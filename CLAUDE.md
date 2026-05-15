# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Aesthetic Loop** is a closed-loop AI experiment: two LLM agents (Bob and Alice) collaborate with a Stable Diffusion image generator (Charly via ComfyUI) to iteratively refine images toward their own evolving aesthetic sense. A vision model (Dylan via Ollama) bridges images to text so Alice can critique them. The human is removed from the loop entirely.

Agent roles:
- **Bob** (`gemma3:12b`) — art director; rewrites prompts, calls `paint_image`
- **Alice** (`mistral-small3.1`) — critic; calls `describe_image`, gives Bob direction
- **Dylan** (`qwen2.5vl:7b`) — vision-only tool, translates images to text
- **Charly** (SDXL via ComfyUI on host `:8188`) — the image generator

## Development Commands

```bash
# Pre-flight GPU check (ROCm)
bash check-gpu.sh

# First-time setup
cp .env.example .env
echo "RENDER_GID=$(getent group render | cut -d: -f3)" >> .env
# Edit .env to set SD_CHECKPOINT to a filename in ComfyUI's models/checkpoints/

# Run the loop
docker compose up

# Watch live output
docker compose logs -f orchestrator

# Verify Ollama is using GPU (not CPU)
docker logs ollama 2>&1 | grep -iE "rocm|gfx|gpu|vram"
docker exec ollama ollama ps

# Re-run after completion (models stay loaded)
docker compose up orchestrator

# Tear down (keep model volumes)
docker compose down

# Tear down and free ~30 GB of model storage
docker compose down -v
```

## Architecture

The orchestrator container runs a CrewAI-based loop. On each iteration:

1. Bob receives the current prompt + Alice's last critique → rewrites/refines the prompt → calls `paint_image`
2. `paint_image` POSTs to ComfyUI REST API (`/prompt`), polls `/history` until done, saves `./output/iter_NNNN.png`
3. Alice receives the image path → calls `describe_image`
4. `describe_image` sends the image to Dylan (Ollama vision model) → returns a text description
5. Alice writes a structured critique → Bob starts the next iteration

All images are saved. `history.json` logs every prompt, critique, and image path.

Key files:
- [orchestrator/src/main.py](orchestrator/src/main.py) — the iteration loop
- [orchestrator/src/agents.py](orchestrator/src/agents.py) — Bob and Alice definitions
- [orchestrator/src/tools.py](orchestrator/src/tools.py) — `paint_image` and `describe_image` tool implementations
- [docker-compose.yml](docker-compose.yml) — Ollama + orchestrator only (ComfyUI is a pre-existing host process)
- [.env.example](.env.example) — all configurable variables

## Configuration

All settings live in `.env`. Key variables:

| Variable | Default | Notes |
|---|---|---|
| `RENDER_GID` | *(required)* | `getent group render \| cut -d: -f3` |
| `COMFYUI_BASE_URL` | `http://host.docker.internal:8188` | use `:8190` for the `zimage` instance |
| `SD_CHECKPOINT` | `v1-5-pruned-emaonly.ckpt` | must exist in ComfyUI's checkpoints dir |
| `BOB_MODEL` | `gemma3:12b` | any Ollama model |
| `ALICE_MODEL` | `mistral-small3.1:latest` | intentionally different from Bob |
| `DYLAN_MODEL` | `qwen2.5vl:7b` | must be a vision-capable model |
| `INITIAL_PROMPT` | mountain landscape… | Bob's starting point for iteration 1 |
| `MAX_ITERATIONS` | `50` | total loop iterations |
| `MILESTONES` | `1,5,10,20,50` | highlighted in logs; all images are saved regardless |
| `HSA_OVERRIDE_GFX_VERSION` | *(commented out)* | set if Ollama falls back to CPU |

## Networking

ComfyUI is **not** managed by this compose file — it runs as a separate host process on `:8188`. The orchestrator container reaches it via `host.docker.internal:8188`. No changes to the existing ComfyUI setup are needed.

