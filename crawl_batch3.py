#!/usr/bin/env python3
"""Batch3 ORG-CRAWL extension for hf-datasets-trees.

Covers 17 new orgs (org models + org datasets) plus finetune/adapter/merge/
quantization trees for 4 anchor models, using the HuggingFace Hub HTTP API.

API rules (verified live, follow exactly):
  - Org datasets: GET /api/datasets?author=ORG&limit=100&sort=lastModified&direction=-1
  - Org models:    GET /api/models?author=ORG&limit=100&sort=trendingScore&direction=-1
  - Model trees:   GET /api/models?filter=base_model:<TYPE>:<ID>&limit=100
                   &sort=trendingScore&direction=-1
    with TYPE in {finetune, adapter, merge, quantization}
    (NOTE: quantization, NOT quantized; sort=trendingScore, NOT sort=trending
    which returns 400; p= param is dead, cursor hops only).
  - Follow the `Link: rel="next"` cursor URL verbatim until gone.
  - author= is exact case-sensitive: probe canonical casing first, skip orgs
    that return empty after the casing probe.
  - Sleep 1.0s between calls; on 429 parse the RateLimit/Retry-After header
    t=<secs>, sleep t+5, retry the same URL. Bearer HF_TOKEN if env present.
  - Single worker only (strictly sequential, no threads).

Resilience: every page is saved to data_batch3/<query>/pNNNN.json plus a
state file with the next cursor, so reruns resume without refetching.
Extraction streams from saved pages (bounded memory even for 70k-model orgs).

Extraction (repo filter):
  - KEEP stripped `dataset:<value>` tag values from model records.
  - KEEP org-dataset ids from datasets calls.
  - DROP all model ids and all `base_model:<...>` tag values.
  - Keep bare slugs (squad_v2 etc.) and owner/repo strings as-is;
    unreachable/private entries are kept as plain strings (no validation).

Outputs (never overwrites batch1/2, committed batch3 tag-sweep,
combined-full, or combined-deduped):
  - data_batch3/              raw per-page JSON + state files + summary.json
  - batch3-orgs-list.txt      3-line # header + deduped sorted org-crawl entries
  - combined-extended-list.txt = sorted dedupe of
    batch1 + batch2 + committed-batch3 + batch3-orgs + combined-full bodies

Usage:
  HF_TOKEN=... python3 crawl_batch3.py [--refresh]
  --refresh  ignore saved pages/state and refetch everything (default: resume).
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

try:
    from huggingface_hub import HfApi  # noqa: F401 (auth/probe path; crawl uses raw HTTP for exact cursor control)
    HAVE_HF_HUB = True
except Exception:  # huggingface_hub not installed -> urllib only
    HAVE_HF_HUB = False

API = "https://huggingface.co/api"
TOKEN = os.environ.get("HF_TOKEN", "")
SLEEP_BETWEEN_CALLS = 1.0
LIMIT = 100

ORGS = [
    "bartowski", "QuantFactory", "mradermacher", "ggml-org", "unsloth",
    "huihui-ai", "Sao10K", "TehVenom", "NousResearch", "arcee-ai",
    "MaziyarPanahi", "mistralai", "microsoft", "allenai", "deepseek-ai",
    "upstage", "MiniMaxAI",
]

ANCHORS = [
    "Qwen/Qwen3-32B",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "deepseek-ai/DeepSeek-R1",
    "NousResearch/Hermes-3-Llama-3.1-8B",
]

TREE_TYPES = ["finetune", "adapter", "merge", "quantization"]

RAW_DIR = "data_batch3"
REFRESH = "--refresh" in sys.argv

_ssl_unverified_logged = False


def _headers():
    h = {"User-Agent": "hf-datasets-trees-batch3/1.0", "Accept": "application/json"}
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    return h


def _parse_429_wait(headers):
    """Extract t=<secs> from RateLimit/Retry-After headers. Returns float secs."""
    cands = []
    for k in headers.keys():
        kl = k.lower()
        if kl in ("retry-after", "x-retry-after") or "ratelimit" in kl:
            cands.append(headers.get(k, ""))
    for v in cands:
        m = re.search(r"(\d+(?:\.\d+)?)", v or "")
        if m:
            t = float(m.group(1))
            if t > 1e9:  # epoch-style reset timestamp -> delta
                t = max(0.0, t - time.time())
            return t
    return 60.0  # fallback when header unparseable


def _http_get(url):
    """GET url with 429 backoff (sleep t+5, retry same URL) + transient retry."""
    global _ssl_unverified_logged
    tries_5xx = 0
    tries_429 = 0
    tries_io = 0
    use_unverified = False
    while True:
        req = urllib.request.Request(url, headers=_headers())
        ctx = ssl._create_unverified_context() if use_unverified else None
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
                return r.read(), r.headers
        except urllib.error.HTTPError as e:
            if e.code == 429 and tries_429 < 15:
                wait = min(_parse_429_wait(e.headers) + 5.0, 900.0)
                print(f"  429 on {url[:100]}... sleep {wait:.0f}s then retry", flush=True)
                time.sleep(wait)
                tries_429 += 1
                continue
            if e.code in (500, 502, 503, 504) and tries_5xx < 5:
                wait = 5 * (2 ** tries_5xx)
                print(f"  {e.code} on {url[:100]}... sleep {wait}s then retry", flush=True)
                time.sleep(wait)
                tries_5xx += 1
                continue
            raise
        except (TimeoutError, ConnectionError, OSError) as e:
            # Socket-level timeout/reset (not wrapped by urllib): bounded retry.
            if tries_io < 8:
                wait = 5 * (2 ** min(tries_io, 4))
                print(f"  IO {type(e).__name__} on {url[:100]}... sleep {wait}s then retry", flush=True)
                time.sleep(wait)
                tries_io += 1
                continue
            raise
        except (ssl.SSLError, urllib.error.URLError) as e:
            # Env has broken SSL verify (repo README notes curl -k); fall back once.
            if not use_unverified:
                use_unverified = True
                if not _ssl_unverified_logged:
                    print("  NOTE: SSL verify failed, using unverified context (env SSL broken)", flush=True)
                    _ssl_unverified_logged = True
                continue
            raise


def _parse_next_link(link_header):
    if not link_header:
        return None
    # Link: <url>; rel="next", <url>; rel="last", ...
    for m in re.finditer(r'<([^>]+)>\s*;\s*rel="([^"]+)"', link_header):
        if m.group(2) == "next":
            return m.group(1)
    return None


def q(base, params):
    return base + "?" + urllib.parse.urlencode(params)


def probe_casing(org):
    """Return canonical-cased author name, or None if empty after probe."""
    seen = []
    for c in (org, org.lower()):
        if c not in seen:
            seen.append(c)
    for cand in seen:
        m_url = q(API + "/models", {"author": cand, "limit": 2,
                                    "sort": "trendingScore", "direction": -1})
        d_url = q(API + "/datasets", {"author": cand, "limit": 2,
                                      "sort": "lastModified", "direction": -1})
        try:
            m_body, _ = _http_get(m_url)
            time.sleep(SLEEP_BETWEEN_CALLS)
            d_body, _ = _http_get(d_url)
            time.sleep(SLEEP_BETWEEN_CALLS)
            m = json.loads(m_body.decode("utf-8"))
            d = json.loads(d_body.decode("utf-8"))
            if (isinstance(m, list) and m) or (isinstance(d, list) and d):
                return cand
        except Exception as e:
            print(f"  probe {cand} error: {e}", flush=True)
    return None


def _qdir(name):
    d = os.path.join(RAW_DIR, "q_" + re.sub(r"[^A-Za-z0-9_.-]+", "_", name))
    os.makedirs(d, exist_ok=True)
    return d


def _state_path(name):
    return os.path.join(_qdir(name), "state.json")


def _load_state(name):
    try:
        with open(_state_path(name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(name, state):
    tmp = _state_path(name) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, _state_path(name))


def extract_datasets_from_models(records, acc):
    """KEEP stripped dataset: tags; DROP model ids + base_model: tags."""
    for m in records:
        if not isinstance(m, dict):
            continue
        for tag in (m.get("tags") or []):
            if isinstance(tag, str) and tag.startswith("dataset:"):
                v = tag[len("dataset:"):].strip()
                if v:
                    acc.add(v)


def extract_ids_from_datasets(records, acc):
    for d in records:
        if isinstance(d, dict) and d.get("id"):
            v = str(d["id"]).strip()
            if v:
                acc.add(v)


def run_query(name, start_url, kind, acc):
    """Fetch all cursor pages for one query, saving each page + cursor state.

    kind: 'models' (extract dataset: tags) or 'datasets' (extract ids).
    Resumes from saved state; acc set accumulates extracted strings.
    Returns (total_records, total_pages).
    """
    qd = _qdir(name)
    st = {} if REFRESH else _load_state(name)
    if st.get("done") and not REFRESH:
        # No network: re-extract from saved pages.
        recs = pages_n = 0
        i = 0
        while True:
            p = os.path.join(qd, f"p{i:04d}.json")
            if not os.path.exists(p):
                break
            with open(p) as f:
                data = json.load(f)
            recs += len(data)
            pages_n += 1
            if kind == "models":
                extract_datasets_from_models(data, acc)
            else:
                extract_ids_from_datasets(data, acc)
            i += 1
        print(f"  {name}: cached {recs} records / {pages_n} pages", flush=True)
        return recs, pages_n
    url = st.get("next", start_url)
    recs = st.get("records", 0)
    pages_n = st.get("pages", 0)
    while url:
        body, headers = _http_get(url)
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            print(f"  WARN {name}: bad JSON page {pages_n}: {e}", flush=True)
            break
        if isinstance(data, dict):
            print(f"  WARN {name}: dict response keys={list(data)[:5]}", flush=True)
            break
        with open(os.path.join(qd, f"p{pages_n:04d}.json"), "w") as f:
            json.dump(data, f)
        recs += len(data)
        if kind == "models":
            extract_datasets_from_models(data, acc)
        else:
            extract_ids_from_datasets(data, acc)
        url = _parse_next_link(headers.get("Link"))
        _save_state(name, {"next": url, "records": recs,
                           "pages": pages_n + 1, "done": url is None})
        pages_n += 1
        if url:
            time.sleep(SLEEP_BETWEEN_CALLS)
    print(f"  {name}: {recs} records / {pages_n} pages", flush=True)
    return recs, pages_n


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)


def main():
    print(f"huggingface_hub HfApi available: {HAVE_HF_HUB}; HF_TOKEN present: {bool(TOKEN)}; refresh={REFRESH}", flush=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    batch3 = set()
    org_stats, tree_stats = {}, {}
    skipped = []
    for org in ORGS:
        print(f"[{org}] probing casing...", flush=True)
        canon = probe_casing(org)
        if canon is None:
            print(f"[{org}] SKIP: empty after casing probe", flush=True)
            skipped.append(org)
            continue
        if canon != org:
            print(f"[{org}] canonical casing -> {canon}", flush=True)
        m_url = q(API + "/models", {"author": canon, "limit": LIMIT,
                                    "sort": "trendingScore", "direction": -1})
        d_url = q(API + "/datasets", {"author": canon, "limit": LIMIT,
                                      "sort": "lastModified", "direction": -1})
        mr, mp = run_query(f"org_models_{safe_name(canon)}", m_url, "models", batch3)
        time.sleep(SLEEP_BETWEEN_CALLS)
        dr, dp = run_query(f"org_datasets_{safe_name(canon)}", d_url, "datasets", batch3)
        time.sleep(SLEEP_BETWEEN_CALLS)
        org_stats[canon] = {"models": mr, "model_pages": mp,
                            "datasets": dr, "dataset_pages": dp}

    for anchor in ANCHORS:
        for t in TREE_TYPES:
            key = f"{anchor} [{t}]"
            t_url = q(API + "/models", {"filter": f"base_model:{t}:{anchor}",
                                        "limit": LIMIT, "sort": "trendingScore",
                                        "direction": -1})
            tr, tp = run_query(f"tree_{safe_name(anchor)}_{t}", t_url, "models", batch3)
            time.sleep(SLEEP_BETWEEN_CALLS)
            tree_stats[key] = {"models": tr, "pages": tp}

    batch3_sorted = sorted(batch3, key=lambda s: (s.lower(), s))
    today = date.today().isoformat()

    with open("batch3-orgs-list.txt", "w") as f:
        f.write(f"# Batch 3 org-crawl - {', '.join(ORGS)} org models/datasets + {len(ANCHORS)} anchor trees (finetune/adapter/merge/quantization)\n")
        f.write("# own org datasets + stripped dataset: tags from org/tree models, deduped; model ids and base_model: tags excluded\n")
        f.write(f"# Generated {today} via HF Hub API (sort=trendingScore/lastModified desc, Link cursor pagination)\n")
        for e in batch3_sorted:
            f.write(e + "\n")

    # ---- combined extended (never touches committed files) ----
    def body(path):
        out = []
        with open(path) as f:
            for line in f:
                line = line.rstrip("\n")
                if line.startswith("#") or not line.strip():
                    continue
                out.append(line.strip())
        return out

    extended = set(body("batch1-list.txt")) | set(body("batch2-list.txt")) \
        | set(body("batch3-list.txt")) | set(batch3_sorted) \
        | set(body("combined-full-pages-list.txt"))
    extended_sorted = sorted(extended, key=lambda s: (s.lower(), s))
    with open("combined-extended-list.txt", "w") as f:
        f.write("# Extended combined list: batch1 + batch2 + committed batch3 tag-sweep + batch3-orgs crawl + combined-full-pages-list bodies, deduped\n")
        f.write("# sorted case-insensitive; format owner/dataset or bare slug; private/gated kept as-is\n")
        f.write(f"# Generated {today}; does NOT replace combined-full-pages-list.txt, combined-deduped-list.txt, or batch3-list.txt\n")
        for e in extended_sorted:
            f.write(e + "\n")

    summary = {
        "date": today,
        "orgs_crawled": org_stats,
        "trees": tree_stats,
        "skipped_orgs": skipped,
        "batch3_orgs_unique": len(batch3_sorted),
        "extended_unique": len(extended_sorted),
    }
    with open(os.path.join(RAW_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print("\n==== BATCH3 ORG-CRAWL SUMMARY ====", flush=True)
    for c, v in org_stats.items():
        print(f"  org {c}: {v['models']} models / {v['datasets']} datasets", flush=True)
    for k, v in tree_stats.items():
        print(f"  tree {k}: {v['models']} models", flush=True)
    print(f"  skipped orgs: {skipped if skipped else 'none'}", flush=True)
    print(f"  batch3-orgs-list.txt unique entries: {len(batch3_sorted)}", flush=True)
    print(f"  combined-extended-list.txt unique entries: {len(extended_sorted)}", flush=True)


if __name__ == "__main__":
    main()
