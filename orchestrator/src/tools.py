import base64
import os
import random
import time
import uuid

import requests

COMFYUI_BASE_URL = os.environ.get("COMFYUI_BASE_URL", "http://host.docker.internal:8188")
WORKFLOW_PATH = os.environ.get("WORKFLOW_PATH", "/workflow.json")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/output")
DYLAN_MODEL = os.environ.get("DYLAN_MODEL", "qwen2.5vl:3b")
DYLAN_HOST = os.environ.get("DYLAN_HOST", "http://dylan:11434")


def paint_image(prompt: str, iter_num: int) -> str:
    with open(WORKFLOW_PATH) as f:
        raw = f.read()

    raw = raw.replace("%PROMPT%", prompt.replace('"', '\\"'))
    workflow = __import__("json").loads(raw)

    # randomise seed so each iteration produces a different image
    for node in workflow.values():
        if node.get("class_type") == "KSampler" and "seed" in node.get("inputs", {}):
            node["inputs"]["seed"] = random.randint(0, 2**32 - 1)

    client_id = str(uuid.uuid4())
    print(f"  [ComfyUI] posting prompt to {COMFYUI_BASE_URL}...")
    resp = requests.post(
        f"{COMFYUI_BASE_URL}/prompt",
        json={"prompt": workflow, "client_id": client_id},
        timeout=30,
    )
    resp.raise_for_status()
    prompt_id = resp.json()["prompt_id"]
    print(f"  [ComfyUI] queued {prompt_id}")

    PAINT_TIMEOUT = 300  # seconds
    deadline = time.monotonic() + PAINT_TIMEOUT
    last_log = time.monotonic()
    LOG_INTERVAL = 15

    while True:
        if time.monotonic() > deadline:
            raise RuntimeError(f"ComfyUI timed out after {PAINT_TIMEOUT}s for {prompt_id}")

        elapsed = time.monotonic() - (deadline - PAINT_TIMEOUT)
        if time.monotonic() - last_log >= LOG_INTERVAL:
            queue = requests.get(f"{COMFYUI_BASE_URL}/queue", timeout=5).json()
            running = len(queue.get("queue_running", []))
            pending = len(queue.get("queue_pending", []))
            print(f"  [ComfyUI] waiting... {elapsed:.0f}s elapsed | running={running} pending={pending}")
            last_log = time.monotonic()

        hist = requests.get(f"{COMFYUI_BASE_URL}/history/{prompt_id}", timeout=10).json()
        if prompt_id in hist:
            print(f"  [ComfyUI] done in {elapsed:.0f}s")
            break
        time.sleep(2)

    outputs = hist[prompt_id]["outputs"]
    image_meta = None
    for node_output in outputs.values():
        if "images" in node_output:
            image_meta = node_output["images"][0]
            break

    if image_meta is None:
        raise RuntimeError(f"No image in ComfyUI output for prompt_id={prompt_id}")

    img_resp = requests.get(
        f"{COMFYUI_BASE_URL}/view",
        params={
            "filename": image_meta["filename"],
            "subfolder": image_meta.get("subfolder", ""),
            "type": image_meta.get("type", "output"),
        },
        timeout=30,
    )
    img_resp.raise_for_status()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"iter_{iter_num:04d}.png")
    with open(out_path, "wb") as f:
        f.write(img_resp.content)

    print(f"  [ComfyUI] saved {out_path}")

    try:
        requests.post(
            f"{COMFYUI_BASE_URL}/free",
            json={"unload_models": True, "free_memory": True},
            timeout=10,
        )
        print("  [ComfyUI] VRAM freed")
    except Exception:
        pass

    return out_path


def describe_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    resp = requests.post(
        f"{DYLAN_HOST}/api/generate",
        json={
            "model": DYLAN_MODEL,
            "prompt": "Describe this image in rich detail: composition, colours, mood, textures, and any notable visual elements.",
            "images": [b64],
            "stream": False,
        },
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()["response"].strip()

    # unload Dylan immediately so ComfyUI has full VRAM for the next paint
    try:
        requests.post(
            f"{DYLAN_HOST}/api/generate",
            json={"model": DYLAN_MODEL, "keep_alive": 0},
            timeout=10,
        )
        print("  [Dylan] model unloaded from VRAM")
    except Exception:
        pass

    return result
