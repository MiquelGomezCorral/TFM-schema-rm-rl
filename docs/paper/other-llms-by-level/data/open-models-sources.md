# Open-weight models: evidence for `open-models.csv`

Gathered 2026-11-26. One row per model in the CSV; one section per model here, one line per cell.

Path prefixes (all absolute roots, so a reader can open each file):

- `C` = `/home/turbotowerlnx/Documents/Master/TFM/TFM-schema-rm-rl`
- `M` = `C/.git/agent-memory` (not tracked by Git)
- `S` = `M/plans/farm-final-20261119/multi-llm-20261124` (study folder: drivers, watcher log, cluster reports)
- `LOG` = `S/small-local-ollama.log` (the local Ollama server's own log, with the llama.cpp load lines)
- `README` = `C/docs/paper/other-llms-by-level/README.md`

What the call logs say: `*.calls.jsonl` in `M/plans/farm-final-20261119/until-fix/runs/multillm-*/L/` carry `model` (the
served name, with `@critic` for the critic role), `model_reported` (the same name echoed by the server) and `cli` (always
null). `provider` is not a name there: it is a dict (`reasoning_sent`, `resends`, `usage`, `thinking_chars`). They hold no
runtime, repository, quantization or GPU, so those facts come from the files below. All counted served names match the
CSV models (checked over every `multillm-*` run folder except smokes).

Local GPU: `nvidia-smi --query-gpu=name,memory.total` gives `NVIDIA GeForce RTX 5070, 12227 MiB`; `LOG:273533` lists
10815 MiB free when gpt-oss-20b loaded.

## Cluster models (UPV cluster "tensor", vLLM)

Common facts:

- Cluster and GPUs: 4x NVIDIA L40S, 46 GB each (`M/workflow.md:805`; `S/a-cluster-report.md:9` "L40S has 46 GB"). The
  packet says 48 GB, the nominal card size; the records say 46 GB.
- Runtime: `vllm==0.34.0`, torch 2.14.0+cu132, own venv `~/llm/venv` (`S/a-cluster-report.md:7`; `README:479`).
- Launch script: `S/serve_vllm.sbatch` (`--gpu-memory-utilization 0.90` unless a later flag overrides it: `S/serve_vllm.sbatch:43-49`, where extra flags come last through `"$@"`). Per-model lines in its header, `S/serve_vllm.sbatch:8-13`.
- The four vLLM serve logs (`~/llm/logs/serve-<job>.log`, with the `Model loading took ... GiB` line) exist only on the
  cluster. No copy is on this disk (searched `M`, `C/docs`, `C/experiments/dev`). On 2026-11-26 one read-only
  `ssh tensor "grep -H 'Model loading took' llm/logs/serve-57174.log llm/logs/serve-57192.log"` filled the two empty
  `weights_gib` cells (Muse Glimmer 30B and Gemma 4 31B, below). The Qwen3.8 27B and gpt-oss-120b cells stay
  checkpoint-based.

### Muse Glimmer 30B

- where / gpu: cluster, 1 GPU. `S/a-cluster-report.md:31` (job 57174, 1 GPU, 65536 context); `README:123` "one cluster L40S".
  The watcher log shows this job served from `S/cluster-watch.log:15` (2026-11-24 23:25:42) to the `scancel 57174` at
  `S/cluster-watch.log:34`; no later job served Muse.
- runtime: vLLM 0.34.0 (above), flag `--reasoning-parser muse_glimmer` (`S/a-cluster-report.md:31`).
- weights: `meta-models/Muse-Glimmer-30B`, BF16, 55.5 GiB (`S/serve_vllm.sbatch:11`; `S/a-cluster-report.md:10`; downloaded
  59.6 GB, `S/a-cluster-report.md:35`). Hub API `https://huggingface.co/api/models/meta-models/Muse-Glimmer-30B`:
  `usedStorage` 59,581,565,169 B = 55.49 GiB; safetensors BF16 29,776,626,688 parameters.
- quantization: online FP8 through `--quantization fp8` (`S/a-cluster-report.md:31`; `README:123` "quantized to FP8 at load").
- weights_gib 32.38: vLLM load log of job 57174, `~/llm/logs/serve-57174.log` on the cluster (2026-11-24 23:23:55):
  "Model loading took 32.38 GiB memory and 29.046795 seconds". Above the 27.7 GiB of 29.78e9 parameters x 1 byte; the log
  does not say why. The sbatch header's "~31 GiB in VRAM" (line 9, for Gemma) was an untested planning figure.
- total_params_b 29.6: model card, `https://huggingface.co/meta-models/Muse-Glimmer-30B`, rows "Total Parameters | ~29.6B" and
  "Number of Parameters | 29.6B (including vision encoder)"; "Perception encoder | ~1.8B param ViT-G/14". The card's own
  numbers are not fully consistent with the Hub's 29.78B safetensors total.
- active_params_b 29.6: card row "Model Architecture | Dense Causal Transformer with Perception Encoder"; the card gives no
  separate active count.

### Gemma 4 31B

- where / gpu: cluster, 1 GPU (`S/a-cluster-report.md:30`; `README:126`). Served by job 57192 (`S/h-cluster-fix-report.md:14`;
  `S/cluster-watch.log:224` `scancel 57192 (gemma-4-31b)`).
- runtime: vLLM 0.34.0.
- weights: `google/gemma-4-31b-it` (lowercase cached copy of `google/gemma-4-31B-it`), BF16 58.3 GiB
  (`S/serve_vllm.sbatch:9`; refreshed download 62.6 GB, `S/a-cluster-report.md:35`). Hub API: safetensors BF16
  31,273,088,876 parameters (x2 B = 58.25 GiB).
- quantization: online FP8 (`--quantization fp8`) plus an FP8 KV cache (`--kv-cache-dtype fp8`), with
  `--gpu-memory-utilization 0.95 --max-num-seqs 16`, context 49152 (`S/h-cluster-fix-report.md:14`;
  `M/known-errors.md:1106`: 7.12 GiB of KV at util 0.90 against 8.39 GiB needed for 49152 tokens).
- weights_gib 31.7: vLLM load log of job 57192, `~/llm/logs/serve-57192.log` on the cluster (2026-11-25 12:43:35):
  "Model loading took 31.7 GiB memory and 46.061257 seconds". Above the 29.1 GiB of 31.27e9 parameters x 1 byte; the log
  does not say why.
- total_params_b 30.7 and active_params_b 30.7: model card `https://huggingface.co/google/gemma-4-31B-it`, Dense Models table
  row "Total Parameters ... 30.7B", "Vision Encoder Parameters ... ~550M", "Layers ... 60". The card lists no active count for
  this dense model (the 3.8B active figure belongs to the 26B A4B model). The Hub total 31.27B includes the vision encoder.

### Qwen3.8 27B

- where / gpu: cluster, 1 GPU (`S/a-cluster-report.md:29`; `README:131`). Jobs: 57189 per `S/h-cluster-fix-report.md:3`
  (the watcher log does not name the job that served `none` to `medium` and the first 79 `max` runs; the log only has
  `serving qwen3.8-27b` at `S/cluster-watch.log:39`), and 57283 for the last 59 `max` runs (`README:214`;
  `S/cluster-watch.log:269`).
- runtime: vLLM 0.34.0; `--reasoning-parser qwen3 --language-model-only --max-num-seqs 16`, context 65536
  (`S/h-cluster-fix-report.md:3`; `M/known-errors.md:1106` for the Mamba cache limit behind `--max-num-seqs 16`).
- weights: `Qwen/Qwen3.8-27B-FP8` (`README:131`; `S/serve_vllm.sbatch:8` "28.7 GiB").
- quantization: FP8, the official checkpoint, no load-time quantization (`README:131`). Hub API
  `https://huggingface.co/api/models/Qwen/Qwen3.8-27B-FP8`: `quantization_config.quant_method` fp8; safetensors F8_E4M3
  24,699,207,680 and BF16 3,082,220,272 parameters (the BF16 part is modules left unquantized).
- weights_gib 28.76: Hub `usedStorage` 30,879,676,248 B / 2^30 = 28.76 GiB; the safetensors counts above give 28.74 GiB
  (3,082,220,272 x 2 B + 24,699,207,680 x 1 B); downloaded size 30.9 GB (`S/a-cluster-report.md:35`). This is the checkpoint
  on disk, not a vLLM load-log value. `--language-model-only` is documented to skip loading the multimodal modules
  (vLLM docs mirror `https://www.mintlify.com/vllm-project/vllm/models/multimodal-models`; official docs not read), so the
  loaded weights are somewhat smaller than 28.76.
- total_params_b 27 and active_params_b 27: model card `https://huggingface.co/Qwen/Qwen3.8-27B`, "Number of Parameters: 27B"
  (Language Model), "a compact, deployment-friendly dense model", "Number of Layers: 64"; Hub safetensors total 27.78B
  includes the vision encoder (`.../api/models/Qwen/Qwen3.8-27B-FP8`). No active count on the card (dense).

### gpt-oss-120b

- where / gpu: cluster, **2 GPUs, tensor parallel 2** (`S/a-cluster-report.md:32`; `README:136` "2 cluster GPUs (tensor parallel
  2)"; `README:222`). Served by job 57193 (`S/h-cluster-fix-report.md:14`; `S/cluster-watch.log:245`). This contradicts the
  packet's "one L40S".
- runtime: vLLM 0.34.0; `--reasoning-parser openai_gptoss`, context 65536, no quantization flag (`S/a-cluster-report.md:32`).
- weights: `openai/gpt-oss-120b`, MXFP4, 60.8 GiB (`S/serve_vllm.sbatch:13`; `README:137`); downloaded 65.3 GB with
  `original/` and `metal/` excluded (`S/a-cluster-report.md:35`; 65.3e9 / 2^30 = 60.82).
- quantization: MXFP4; model card `https://huggingface.co/openai/gpt-oss-120b`: "post-trained with MXFP4 quantization of the
  MoE weights"; Hub config `quant_method: mxfp4`.
- weights_gib 60.8: checkpoint size on disk, not a load-log value. Whether vLLM keeps MXFP4 on Ada GPUs or converts it was
  not checked, so the loaded size per GPU is unknown.
- total_params_b 117 and active_params_b 5.1: model card, "(117B parameters with 5.1B active parameters)". Hub safetensors
  total 116,829,156,672; `num_experts_per_tok` 4.

## Local models (this PC, one RTX 5070 12 GB, user-space Ollama 0.40.18)

Common facts:

- Runtime: `ollama --version` (client and server) prints `ollama version is 0.40.18`, from
  `/home/turbotowerlnx/.local/ollama-0.40.18/bin/ollama` on port 11500 (`S/tools/small-local-run.sh:9-10,15-19`; `README:142`).
  The load lines in `LOG` are llama.cpp's, started by Ollama as `lib/ollama/llama-server` (`LOG:847`, `LOG:90917`,
  `LOG:140107`, `LOG:273405`). The separate system Ollama on port 11434 holds only `nomic-embed-text`.
- Common settings: `-c 98304 -np 2` (49152 per slot x 2) for Qwen3.5, Gemma 4 12B and gpt-oss-20b; `-c 49152 -np 1` for
  Llama; `--cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on` for all (same command lines).
- `weights` come from `ollama list` and `ollama show <tag>` (read-only calls on port 11500) and the manifests in
  `/home/turbotowerlnx/.local/ollama-0.40.18/models/manifests/registry.ollama.ai/library/`; the loaded blob digest in the
  `--model` argument of each `llama-server` line matches the manifest's model layer.
- `weights_gib` is the load log's `print_info: file size` (the tensors llama.cpp loaded, 2 decimals). The GGUF file from the
  manifest is slightly larger (it includes the header and vocabulary). Both are in the lines below.
- Overflow: only gpt-oss-20b overflowed to the CPU in its study configuration. The other three loaded all layers on the GPU
  (`offloaded N/N layers`) and fit with room to spare (the `projected to use ... vs ... free device memory` lines below). In
  every load some tensors are `CPU_Mapped`: the token-embedding table mapped from the file (or a host copy of it), which is
  not a layer overflow. The README statement that Llama at 2 slots would put 22% on the CPU (`README:151`) and the Q6_K
  trial (`LOG:167-171`: `offloaded 32/33 layers`, 5701.34 MiB on CUDA0 and 581.63 MiB host-mapped) were configurations that the
  study did not use.

### Qwen3.5 9B (Q4)

- weights: `qwen3.5:9b-q4_K_M` (`ollama list`: 6.6 GB; blob `sha256-02d45dc1cf45...`, `LOG:847`); GGUF file 5,629,109,120 B =
  5.243 GiB (manifest); projector layer 921,704,832 B = 0.858 GiB loaded with `--mmproj` (`LOG:847`, `LOG:878`
  "estimated worst-case memory usage of mmproj is 1152.01 MiB", `LOG:1103` "loaded multimodal model").
- quantization: Q4_K_M: `ollama show` "quantization Q4_K_M"; `LOG:937` "file type = Q4_K - Medium".
- weights_gib 5.23: `LOG:938` "file size = 5.23 GiB (5.02 BPW)". Consistent with `LOG:1024-1025` (545.62 + 4812.25 MiB =
  5.23 GiB).
- Placement: `LOG:1023` "offloaded 33/33 layers to GPU"; `LOG:886` projected 7042 MiB vs 10316 MiB free. No overflow.
- total_params_b 8.95: `LOG:998` "model params = 8.95 B" (`ollama show`: 9.0B; card `https://huggingface.co/Qwen/Qwen3.5-9B`
  "Number of Parameters: 9B"). active_params_b 8.95: dense, `LOG:977` "n_expert = 0".

### Llama 3.1 8B Instruct (Q5)

- weights: `llama3.1:8b-instruct-q5_K_M` (`ollama list`: 5.7 GB; blob `sha256-1ae48274baaf...`, `LOG:90917`); GGUF file
  5,732,992,128 B = 5.339 GiB.
- quantization: Q5_K_M: `ollama show`; `LOG:90985` "file type = Q5_K - Medium".
- weights_gib 5.33: `LOG:90986` "file size = 5.33 GiB (5.70 BPW)".
- Placement: `LOG:91055` "offloaded 33/33 layers to GPU"; `LOG:90946` projected 8662 MiB vs 10815 MiB free. No overflow.
- total_params_b 8.03: `LOG:91038` "model params = 8.03 B" (card `https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct`: 8B).
  active_params_b 8.03: dense, `LOG:91024` "n_expert = 0".

### Gemma 4 12B (Q4)

- weights: `gemma4:12b-it-q4_K_M` (`ollama list`: 8.0 GB; blob `sha256-bb722270d543...`, `LOG:140107`); GGUF file 7,381,383,680 B =
  6.874 GiB. Also loaded: projector 175,115,616 B = 0.163 GiB (`--mmproj`, `LOG:140574` "loaded multimodal model") and an MTP draft
  model, blob `sha256-7008a656050b...`, 465,109,152 B (`--spec-type draft-mtp --spec-draft-n-max 3
  --spec-draft-model`, `LOG:140107`), Q8_0, "file size = 428.53 MiB" (`LOG:140391-140392`), 428.53 MiB on CUDA0
  (`LOG:140471-140473`) with speculative decoding active (`LOG:140585`).
- quantization: Q4_K_M: `ollama show`; `LOG:140214` "file type = Q4_K - Medium".
- weights_gib 6.86: `LOG:140215` "file size = 6.86 GiB (4.95 BPW)"; `LOG:140296` CUDA0 7024.41 MiB = 6.86 GiB (the 787.50 MiB
  `LOG:140295` is a host-mapped copy of the tied embeddings).
- Placement: `LOG:140294` "offloaded 49/49 layers to GPU"; `LOG:140150` projected 8672 MiB vs 10815 MiB free. No overflow.
- total_params_b 11.91: `LOG:140275` "model params = 11.91 B" (card `https://huggingface.co/google/gemma-4-12B-it`: 11.95B).
  active_params_b 11.91: the card lists it under "Dense Models" with no active count.

### gpt-oss-20b

- weights: `gpt-oss:20b` (`ollama list`: 13 GB; blob `sha256-8ecb5d4ad617...`, `LOG:273405`; the running `llama-server` for the
  `high` level uses the same blob); GGUF file 13,793,422,816 B = 12.846 GiB.
- quantization: MXFP4: `ollama show` "quantization MXFP4"; `LOG:273531` prints "file type = unknown, may not work" for it
  (llama.cpp has no name for it there).
- weights_gib 12.83: `LOG:273532` "file size = 12.83 GiB (5.27 BPW)"; placement lines `LOG:273613-273634` sum to 4,879.66 MiB
  host-mapped (10 x 134.82 + 9 x 269.65 + 1104.61) plus 8,261.60 MiB CUDA0 = 13,141.26 MiB = 12.833 GiB.
- Overflow: `LOG:273435` "projected to use 13559 MiB of device memory vs. 10815 MiB of free device memory";
  `LOG:273489` "CUDA0 (NVIDIA GeForce RTX 5070): 25 layers (11 overflowing), 9784 MiB used, 1030 MiB free";
  `LOG:273613` "offloaded 25/25 layers to GPU" (the overflow is expert tensors kept in host memory). CPU share =
  4,879.66 / 13,141.26 = 37.1%. Same numbers as `M/workflow.md:1294`, which also says `ollama ps` showed ~13%.
- total_params_b 20.91: `LOG:273594` "model params = 20.91 B" (card `https://huggingface.co/openai/gpt-oss-20b`: "21B").
  active_params_b 3.6: card "(21B parameters with 3.6B active parameters)". GGUF: `n_expert` 32, `n_expert_used` 4
  (`LOG:273506-273508`).

## Cells filled from the cluster logs, and cells not from a load log

- `weights_gib` for Muse Glimmer 30B (32.38) and Gemma 4 31B (31.7): measured by vLLM at load (the checkpoints are BF16 and
  vLLM quantizes to FP8, so the checkpoint sizes, 55.5 and 58.3 GiB, are not the loaded size). The logs are on the cluster only.
- Cells filled with a checkpoint size and not a load-log value: Qwen3.8 27B (28.76) and gpt-oss-120b (60.8). The CSV note of
  each says so.

## Records that contradict the packet

- gpt-oss-120b ran on 2 cluster GPUs (tensor parallel 2), not one L40S (`README:136`, `S/a-cluster-report.md:32`).
- The L40S is recorded as 46 GB, not 48 GB (`M/workflow.md:805`, `S/a-cluster-report.md:9`).
- `README:161`, `README:239`, `README:316`, `README:508` and `README:518` said about 13% of gpt-oss-20b runs on the CPU; the load log
  says 37.1% in host memory (`M/workflow.md:1294` already records this). The README now says 37.1%.
- Gemma 4 12B and Qwen3.5 9B also load a vision projector, and Gemma 4 12B a speculative-decoding draft model, beside the
  text weights; the packet and README speak only of the text model.

Not touched: no model was loaded, pulled, run or stopped; no `/api/generate` or `/api/chat` call; `.env` not read; SSH only for the one read-only grep of the two cluster load logs (2026-11-26).
