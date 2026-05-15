# Aesthetic Loop

An experiment in emergent machine aesthetics. Two language model agents — Bob and Alice — collaborate in a closed feedback loop with a Stable Diffusion image generator, iteratively refining images toward their own evolving sense of beauty.

---

## Concept

Most AI image generation is a one-shot process: a human writes a prompt, a model produces an image. This project removes the human from the loop and asks: *what happens when two agents with different aesthetic sensibilities are left to improve an image on their own — indefinitely?*

The experiment is less about producing a specific beautiful image and more about watching the trajectory. What do the agents converge on? Do they agree? Do they surprise us? The milestone images at iterations 1, 5, 10, 20, and 50 tell that story.

---

## The Cast

| Name | Role | Model |
|---|---|---|
| **Bob** | Art director. Writes and refines prompts for the image generator. Absorbs Alice's critique and decides what to change. | `gemma3:12b` |
| **Alice** | Aesthetic critic. Evaluates each image, identifies what works and what doesn't, and gives Bob concrete, specific direction. | `mistral-small3.1` |
| **Dylan** | Silent describer. A vision model that translates images into rich text so Alice has something concrete to critique. Not an agent — a tool. | `qwen2.5vl:7b` |
| **Charly** | The painter. A Stable Diffusion model running inside ComfyUI that turns Bob's prompts into images. Has no opinion of his own. | SDXL via ComfyUI |

Bob and Alice are backed by different model families intentionally. Divergent architectures produce more interesting creative tension than two instances of the same model.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker: aesthetic_net                 │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │              orchestrator container               │  │
│  │                                                   │  │
│  │   ┌─────────┐   prompt   ┌─────────────────────┐ │  │
│  │   │   Bob   │──────────▶ │  paint_image (tool) │ │  │
│  │   │ (agent) │            └──────────┬──────────┘ │  │
│  │   └────▲────┘                       │ HTTP POST  │  │
│  │        │ critique                   │            │  │
│  │   ┌────┴────┐            ┌──────────▼──────────┐ │  │
│  │   │  Alice  │◀── text ── │ describe_img (tool) │ │  │
│  │   │ (agent) │            └──────────┬──────────┘ │  │
│  │   └─────────┘                       │ HTTP POST  │  │
│  └─────────────────────────────────────┼────────────┘  │
│                                        │               │
│  ┌─────────────────┐    host gateway   │               │
│  │  ollama (rocm)  │                   │               │
│  │  Bob / Alice /  │                   │               │
│  │  Dylan models   │                   │               │
│  └─────────────────┘                   │               │
└────────────────────────────────────────┼───────────────┘
                                         │ host.docker.internal
                            ─ ─ ─ ─ ─ ─ ▼ ─ ─ ─ ─ ─ ─ ─
                            │         HOST                │
                            │                             │
                            │  ComfyUI  :8188  ◀── ──────┘
                            │  (already running,          │
                            │   not managed here)         │
                            └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
```

### One loop iteration

```
Bob thinks → writes prompt → Charly paints → Dylan looks → Alice critiques → Bob thinks → …
```

In detail:

1. **Bob** receives the current prompt and Alice's last critique. He rewrites or refines the prompt, then calls the `paint_image` tool.
2. **`paint_image`** POSTs the prompt to the ComfyUI REST API (`/prompt`), polls `/history` until generation is complete, downloads the PNG, and saves it to `./output/iter_NNNN.png`.
3. **Alice** receives the image path and calls `describe_image`.
4. **`describe_image`** sends the image to Dylan (a local vision model via Ollama) and returns a rich textual description.
5. **Alice** reads Dylan's description and writes a structured critique: what works, what should change, one concrete suggestion for Bob.
6. Bob receives Alice's critique. The next iteration begins.

All images are saved. A `history.json` log records every prompt, critique, and image path.

---

## Stack

| Component | Technology | Where it runs |
|---|---|---|
| Agent framework | CrewAI | orchestrator container |
| LLM inference | Ollama (ROCm) | ollama container |
| Image generation | ComfyUI + Stable Diffusion | **host, already running on :8188** |
| GPU | AMD Radeon (ROCm 6.4) | host |

### Why ComfyUI is not in this compose file

ComfyUI is already running as a separate Docker container on the host at `localhost:8188` and has its own working setup — ROCm drivers, model volumes, custom nodes — that should not be disturbed. The orchestrator reaches it via `host.docker.internal:8188`, a standard Docker mechanism that resolves to the host's gateway IP from inside a container.
---

## Project Layout

```
aesthetic-loop/
├── docker-compose.yml          # Ollama + orchestrator only
├── .env.example                # copy to .env before first run
├── check-gpu.sh                # ROCm pre-flight diagnostic
├── output/                     # generated images land here (bind-mounted)
└── orchestrator/
    ├── Dockerfile
    ├── requirements.txt
    └── src/
        ├── main.py             # iteration loop
        ├── agents.py           # Bob and Alice definitions
        └── tools.py            # paint_image and describe_image tools
```

---

## Getting Started

**Prerequisites:** Docker with Compose v2, AMD Radeon GPU, ComfyUI already running on `:8188`.

```bash
# 1. Run the pre-flight GPU check
bash check-gpu.sh

# 2. Configure
cp .env.example .env

# Add your render group GID (required for ROCm device access)
echo "RENDER_GID=$(getent group render | cut -d: -f3)" >> .env

# Set your SD checkpoint filename (must exist in ComfyUI's models/checkpoints/)
# Edit .env and update SD_CHECKPOINT

# 3. Start
docker compose up
```

On first start, `ollama-pull` downloads the three models (~30 GB total). Subsequent starts are instant — models live on a named Docker volume.

Images appear in `./output/` as `iter_0001.png`, `iter_0002.png`, etc.

---

## Configuration

All settings live in `.env`. Key ones:

| Variable | Default | Notes |
|---|---|---|
| `RENDER_GID` | *(required)* | `getent group render \| cut -d: -f3` |
| `COMFYUI_BASE_URL` | `http://host.docker.internal:8188` | swap to `:8190` for the zimage instance |
| `SD_CHECKPOINT` | `v1-5-pruned-emaonly.ckpt` | filename in ComfyUI's checkpoints dir |
| `BOB_MODEL` | `gemma3:12b` | any model available in Ollama |
| `ALICE_MODEL` | `mistral-small3.1:latest` | intentionally different from Bob |
| `DYLAN_MODEL` | `qwen2.5vl:7b` | must be a vision-capable model |
| `INITIAL_PROMPT` | mountain landscape… | Bob's starting point for iteration 1 |
| `MAX_ITERATIONS` | `50` | total iterations to run |
| `MILESTONES` | `1,5,10,20,50` | highlighted in logs (all images are saved) |
| `HSA_OVERRIDE_GFX_VERSION` | *(commented out)* | set if Ollama falls back to CPU |

---

## Useful Commands

```bash
# Watch the loop in real time
docker compose logs -f orchestrator

# Verify Ollama is using the GPU (not CPU)
docker logs ollama 2>&1 | grep -iE "rocm|gfx|gpu|vram"
docker exec ollama ollama ps

# Re-run the loop after it finishes (models stay loaded)
docker compose up orchestrator

# Stop everything
docker compose down

# Remove downloaded models and free ~30 GB
docker compose down -v
```