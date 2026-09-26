# HF Datasets – full page crawl for 29 users/orgs

Every dataset used in their models + datasets they made + up-line base models + down-line derivatives.
Whole pages grabbed via Hub API cursor pagination, trees split finetune/adapter/merge/quantized, sort=trending.

## Orgs (29)
Batch1 (14): Delta-Vector, Guilherme34, jondurbin, ZeroXClem, Jackrong, DavidAU, nightmedia, Goekdeniz-Guelmez, empero-ai, soob3123, neural-bulos, SubMaroon, EldritchLabs, 0xA50C1A1
Batch2 (15): Qwen, ai21labs, TokenRhythm, sequelbox, Blackfrost-AI, win10, vcruz305, ValiantLabs, nvidia, google, facebook, FacebookAI, facebook-llama, meta-llama, ProCreations

## Files
- `batch1-list.txt` – curated batch1 (712)
- `batch2-list.txt` – curated batch2 (~500)
- `combined-deduped-list.txt` – old merge (1196)
- `combined-full-pages-list.txt` – **full page crawl, 3787 unique** (authoritative)
- `data/` – raw API dumps (618 files, 25M, git-ignored after push? currently committed): org_models/datasets per org + tree per base model + summaries

## Page shapes (as requested)
- Model: `https://huggingface.co/Qwen/Qwen3.8-27B` – tags, Model tree (Adapters 117 / Finetunes 394-395 / Merges 19 / Quantizations 1225), eval datasets, Spaces
- Tree: `https://huggingface.co/models?other=base_model:finetune:Qwen/Qwen3.8-27B` – website param is `other=`; **API param is `filter=base_model:<type>:ID`** (`other=` returns unfiltered trending – verified). Sort: `sort=trendingScore&direction=-1` matches `?sort=trending`, pages `p=0..13` = cursor `Link: rel="next"`.
- Org datasets: `https://huggingface.co/Qwen/datasets` – `api/datasets?author=Qwen`, 11 repos, sort Recently updated
- Org models: `https://huggingface.co/Qwen/models` – `api/models?author=Qwen`, 468 repos, 16 pages `p=0..15`
- Sorts: Recently updated = `lastModified`, Trending = `trendingScore`

## Crawl totals
- Qwen: 468 models / 11 datasets; Qwen3.8-27B tree 395 finetune + 117 adapter + 19 merge + 1225 quantized = 1756
- Batch1 orgs: Delta 114/131, Guilherme 317/84, jondurbin 172/29, ZeroXClem 187/0, Jackrong 156/30, DavidAU 395/0, nightmedia 502/0, Goekdeniz 196/41, empero 27/10, soob 37/13, neural-bulos 2/0, SubMaroon 13/10, Eldritch 21/0, 0xA50C1A1 18/0
- Batch2 orgs: 5075 models / 622 datasets (nvidia 943/325, google 1134/72, facebook 2359/124, meta-llama 70/11, etc.)
- `combined-full-pages-list.txt`: ONLY `dataset:` tags + org dataset IDs + curated lists. Model IDs / `base_model:` IDs excluded. No-slash benchmark tags kept (squad_v2, boolq, etc.).

## Notes
- Foundations (Qwen/google/meta/nvidia) pretraining largely untagged; flagship `dataset:` hits are WorldPM/AgentWorld/WebWorld, Nemotron splits, FLAN, ViT/imagenet, wav2vec2/librispeech, bart/cnn_dailymail, roberta/bookcorpus/wikipedia.
- Quants inherit, ~0 new datasets; merges/finetunes add the long tail (openbmb, TeichAI, armand0e, PocketDoc, NewEden, etc.).
- Rate limit 500/5min respected (0.5-2s sleep, 429 backoff). curl -k (env SSL verify broken).

## Batch3 org-crawl (17 orgs + 4 anchor trees, 2026-09-25)

Script: `crawl_batch3.py` (raw per-page dumps + cursor state in `data_batch3/`,
resumable). Output `batch3-orgs-list.txt` (**6641 unique**) and
`combined-extended-list.txt` (**11375 unique** = batch1 + batch2 + committed
batch3 tag-sweep + batch3-orgs + combined-full bodies, deduped). Committed
`batch3-list.txt` (tag sweep), `combined-full-pages-list.txt` and
`combined-deduped-list.txt` were NOT overwritten.

Orgs (models/datasets): bartowski 2462/0, QuantFactory 1420/0, mradermacher
70307/0, ggml-org 199/1, unsloth 1460/15, huihui-ai 186/13, Sao10K 34/3,
TehVenom 43/0, NousResearch 126/39, arcee-ai 204/63, MaziyarPanahi 2816/52,
mistralai 75/4, microsoft 544/118, allenai 970/1287, deepseek-ai 105/2,
upstage 26/6, MiniMaxAI 21/7. No orgs skipped (all non-empty after casing probe).

Anchor trees (finetune/adapter/merge/quantization): Qwen3-32B 585/460/19/0,
Mistral-7B-Instruct-v0.3 538/890/27/0, DeepSeek-R1 326/122/5/0,
Hermes-3-Llama-3.1-8B 39/287/48/0.

API corrections vs old notes: tree filter type is `quantization` (not
`quantized`); sort must be `sort=trendingScore&direction=-1` (`sort=trending`
returns 400); `p=` page param is dead, cursor `Link: rel="next"` hops only;
`author=` is exact case-sensitive (probe casing first); 429 backoff via
RateLimit/Retry-After header (sleep t+5, retry same URL); 1.0s sleep, single
worker. All four `quantization` trees returned 0 for these anchors.

## Rebuild 2026-09-26: combined-extended-list.txt refreshed (64,325 unique)

Concurrent session expanded `batch3-list.txt` 2714 -> 57360 via deep per-tag
sweep (commit 0035b03), which left `combined-extended-list.txt` (11375) stale
— 52,950 batch3 entries missing. Rebuilt as byte-exact union of batch1 +
batch2 + batch3 + batch3-orgs + combined-full + combined-deduped bodies,
deduped, case-insensitive sorted. Verified: 64,325 unique, 0 `base_model:` /
`dataset:` leaks, 0 dupes, 0 sort disorders. Source lists untouched.
