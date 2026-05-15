# Aesthetic Loop — Design

## What it is

A closed-loop AI art experiment. Two LLM agents (Bob and Alice) collaborate with a Stable Diffusion image generator (Charly, via ComfyUI) to iteratively refine images toward their own evolving aesthetic sense. A vision model (Dylan) bridges images to text so Alice can critique what was actually painted. The human is removed from the loop.

## Loop mechanics

Each iteration runs in strict sequence:

```
Bob.think()       → refined prompt text
paint_image()     → PNG saved to /output/iter_NNNN.png
describe_image()  → plain-text description of the image
Alice.critique()  → structured critique fed back to Bob
```

Bob receives only the **last critique** — not the full history. This keeps prompts focused and avoids context bloat. `history.json` is written atomically after every iteration so a partial run is always recoverable.

## Agents

### Bob (`gemma3:12b`) — art director

System prompt instructs Bob to output **only** the prompt text (no preamble, no quotes), use comma-separated descriptive phrases, and make targeted edits based on Alice's direction rather than rewriting from scratch. Iteration 1 seeds from `INITIAL_PROMPT`; subsequent iterations carry the previous prompt plus Alice's critique.

### Alice (`mistral-small3.1:latest`) — aesthetic critic

System prompt requires exactly three structured sections: `WORKS`, `CHANGE`, `DIRECTION`. Alice receives Dylan's plain-text description (not the raw image). The `DIRECTION` section must be something Bob can act on directly in a prompt — no vague suggestions.

### Dylan (`qwen2.5vl:3b`) — vision bridge

Not an agent — a stateless tool. Called once per iteration via Ollama's `/api/generate` with the image base64-encoded in the request body. Returns a free-form description. The small 3B model was chosen to minimise VRAM cost; quality is acceptable for the task (conveying composition, colour, mood to Alice).

## VRAM sequencing

The GPU (AMD RX 7900 XT, 20 GB VRAM) is shared by all four consumers:

| Consumer | VRAM footprint |
|---|---|
| Charly (SDXL via ComfyUI) | ~9 GB |
| Bob (`gemma3:12b`) | ~8.3 GB |
| Alice (`mistral-small3.1:latest`) | ~17 GB |
| Dylan (`qwen2.5vl:3b`) | ~3.2 GB |

No two of these fit simultaneously. The solution is **strict serial occupancy**: each model loads, runs, then immediately evicts itself before the next one loads.

```
Bob thinks   (8.3 GB) → POST /api/generate keep_alive=0  → 0 GB
Charly paints (9 GB)  → POST /free unload_models=true    → 0 GB
Dylan describes (3.2 GB) → POST /api/generate keep_alive=0 → 0 GB
Alice critiques (17 GB) → POST /api/generate keep_alive=0 → 0 GB
repeat
```

The `keep_alive=0` call is made to each Ollama container after the response is received. ComfyUI's `/free` endpoint is called after the image is saved, not before — painting must complete first.

### Why three separate Ollama containers

Bob, Alice, and Dylan each run in their own `ollama/ollama:rocm` container. All share a single named Docker volume (`ollama_models`) so model files are downloaded once and visible to all three. The separation exists so each container holds its own Ollama process, which means its own VRAM allocation state. This made debugging VRAM lifecycle much simpler, and keeps the door open to running agents concurrently if a future iteration changes the sequencing.

### Why not keep models warm

Keeping any model in VRAM while another loads is fatal on this budget. The worst-case overlap is Alice (17 GB) + Bob (8.3 GB) = 25.3 GB, which reliably crashes Bob's HIP runner. Even smaller overlaps cause instability. Cold reloads are fast (Bob: ~2s from NVMe; Dylan: ~3s) so the cost is acceptable.

## ComfyUI integration

The workflow is loaded from `/workflow.json` (mounted read-only). The positive CLIPTextEncode node contains the sentinel `%PROMPT%` which is replaced via string substitution before each request. The KSampler seed is randomised at runtime so every iteration produces a different image even if the prompt is identical.

The API interaction:

1. `POST /prompt` with the modified workflow JSON and a `client_id` UUID
2. Poll `GET /history/{prompt_id}` every 2 seconds until the job appears
3. Walk the outputs dict to find the first node with an `images` list
4. `GET /view?filename=…&subfolder=…&type=…` to download the PNG
5. `POST /free` to evict the SDXL checkpoint from VRAM

The queue is cleared (`POST /queue {"clear": true}`) and any in-flight job interrupted (`POST /interrupt`) at orchestrator startup to avoid inheriting stale state from a previous run.

## Tradeoffs made during development

**`/free` after each paint.** Calling ComfyUI's `/free` forces the SDXL checkpoint (~9 GB) to reload from disk on the next iteration (~16–22s). The alternative — keeping ComfyUI warm — blocks Alice from loading her 17 GB model. At current iteration times (~3 min total), 22s of reload is not the bottleneck; Alice's inference is.

**Dylan at 3B, not 7B.** The 7B vision model was pulled initially but the 3B was chosen to minimise VRAM and reload time. Description quality is adequate for Alice's purposes — she needs composition and mood, not pixel-level accuracy.

**No streaming.** All Ollama calls use `stream: false`. This simplifies error handling and makes timeouts straightforward. The 600s read timeout on `_chat()` is a last-resort guard; normal inference is well under 60s.

**Bob sees only the last critique.** Accumulating the full history would grow the context window each iteration and bias Bob toward the first image's aesthetics. The last critique carries enough signal for targeted refinement.

**`restart: "no"` on the orchestrator.** An error (ComfyUI timeout, Ollama 500) should stop the run, not silently re-queue a new generation from iteration 1. The operator restarts manually after inspecting logs.

**`ollama-pull` pulls to bob's host only.** The `ollama-pull` init container connects to `http://bob:11434` and pulls all three models there. Since all containers mount the same `ollama_models` volume, the files are immediately visible to alice and dylan without a second pull.

## Known issues

**Dylan occasionally refuses to describe the image** ("I'm sorry, but I'm unable to see the image…"). This appears to be a model behaviour edge case with `qwen2.5vl:3b` rather than a pipeline bug — the image bytes are correctly base64-encoded and included in the request. When it occurs, Alice receives a near-empty description and produces a low-signal critique; Bob then tends to make minimal changes. Switching to a larger vision model (`qwen2.5vl:7b`) would likely reduce this, at the cost of more VRAM and longer reload times.

**Alice is 54%/46% CPU/GPU.** At 17 GB, `mistral-small3.1:latest` exceeds the VRAM available after driver and process overhead (~9.4 GB free when Alice loads). Ollama offloads roughly half the layers to GPU and runs the rest on CPU. Alice is still faster than all-CPU, but not as fast as a model that fits entirely in VRAM. A model at or under ~8 GB (e.g. `mistral-nemo:latest`) would run fully on GPU at the cost of potentially less nuanced critiques.
