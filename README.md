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
Bob thinks → writes prompt → Charly paints → Dylan describes → Alice critiques → Bob thinks → …
```

For the full architecture and implementation detail, see [design.md](design.md).

---

## Stack

| Component | Technology | Where it runs |
|---|---|---|
| Orchestrator | Plain Python loop | orchestrator container |
| LLM inference | Ollama (ROCm) | ollama container |
| Image generation | ComfyUI + Stable Diffusion | **host, already running on :8188** |
| GPU | AMD Radeon (ROCm 6.4) | host |

ComfyUI is not in this compose file — it runs as a separate host process at `localhost:8188` and is reached from inside the container via `host.docker.internal:8188`. No changes to the existing ComfyUI setup are needed.

---

## Project Layout

```
aesthetic-loop/
├── docker-compose.yml          # Ollama + orchestrator only
├── .env.example                # copy to .env before first run
├── check-gpu.sh                # ROCm pre-flight diagnostic
├── workflow.json               # your ComfyUI workflow export (gitignored)
├── output/                     # generated images land here (bind-mounted)
└── orchestrator/
    ├── Dockerfile
    ├── requirements.txt
    └── src/
        ├── main.py             # iteration loop
        ├── agents.py           # Bob and Alice
        └── tools.py            # paint_image and describe_image
```

---

## Getting Started

**Prerequisites:** Docker with Compose v2, AMD Radeon GPU, ComfyUI already running on `:8188`.

```bash
# 1. Run the pre-flight check
bash check-gpu.sh

# 2. Export your ComfyUI workflow
#    File → Save (API Format) → workflow.json
#    Make sure the positive CLIPTextEncode node contains the text %PROMPT%

# 3. Configure
cp .env.example .env
echo "RENDER_GID=$(getent group render | cut -d: -f3)" >> .env
# Edit .env and set SD_CHECKPOINT to your checkpoint filename

# 4. Start
docker compose up
```

On first start, `ollama-pull` downloads the three models (~30 GB total). Subsequent starts are instant — models live on a named Docker volume.

Images appear in `./output/` as `iter_0001.png`, `iter_0002.png`, etc. Every prompt, description, and critique is logged to `./output/history.json`.

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
