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
