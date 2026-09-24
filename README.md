# HF Datasets – full trees for 29 users/orgs

Every dataset used in their models + datasets they made + up-line base models + down-line derivatives.

## Batch 1 (14)
Delta-Vector, Guilherme34, jondurbin, ZeroXClem, Jackrong, DavidAU, nightmedia, Goekdeniz-Guelmez, empero-ai, soob3123, neural-bulos, SubMaroon, EldritchLabs, 0xA50C1A1
-> `batch1-list.txt` (712 unique)

## Batch 2 (15)
Qwen, ai21labs, TokenRhythm, sequelbox, Blackfrost-AI, win10, vcruz305, ValiantLabs, nvidia, google, facebook, FacebookAI, facebook-llama, meta-llama, ProCreations
-> `batch2-list.txt` (~500 lines, nvidia 325 own included truncated to high-signal set, google/facebook own sets included)

## Combined
`combined-deduped-list.txt` – 1196 unique slugs, `owner/dataset`, sorted case-insensitive.

## Method
HF MCP: `hf_fs ls hf://models|datasets/OWNER --limit 1000`, `hub_repo_details overview` batched, `hub_repo_search`, `hf_fs search`.
Non-quant originals carry `dataset:` tags; GGUF/EXL2/MLX/quants inherit only.
Upstream = base_model 1-2 levels. Downstream = models listing theirs as base (mostly quants, 0 new except Veritas +2, Qwable +3).
Foundation orgs (Qwen/google/meta/nvidia) pretraining corpora largely untagged – own eval/bench sets listed.

## Coverage notes
- DavidAU 175+/300+, nightmedia 338+/350+, Qwen 424+/1000+, google/facebook 1000+ models – truncated, high-signal sampled.
- Private/gated marked `# private/gated` / `# dangling`.
- Re-run `ls` with larger limits to refresh.
