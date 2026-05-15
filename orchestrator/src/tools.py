import base64
import os
import random
import time
import uuid

import requests

COMFYUI_BASE_URL = os.environ.get("COMFYUI_BASE_URL", "http://host.docker.internal:8188")
WORKFLOW_PATH = os.environ.get("WORKFLOW_PATH", "/workflow.json")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/output")
DYLAN_MODEL = os.environ.get("DYLAN_MODEL", "qwen2.5vl:7b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")


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
    resp = requests.post(
        f"{COMFYUI_BASE_URL}/prompt",
        json={"prompt": workflow, "client_id": client_id},
        timeout=30,
    )
    resp.raise_for_status()
    prompt_id = resp.json()["prompt_id"]

    print(f"  [ComfyUI] queued prompt_id={prompt_id}, polling...")
    while True:
        hist = requests.get(f"{COMFYUI_BASE_URL}/history/{prompt_id}", timeout=10).json()
        if prompt_id in hist:
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

    # Free VRAM so Ollama can use the GPU for inference
    try:
        requests.post(
            f"{COMFYUI_BASE_URL}/free",
            json={"unload_models": True, "free_memory": True},
            timeout=10,
        )
        print("  [ComfyUI] models unloaded from VRAM")
    except Exception as e:
        print(f"  [ComfyUI] /free call failed (non-fatal): {e}")

    return out_path


def describe_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": DYLAN_MODEL,
            "prompt": "Describe this image in rich detail: composition, colours, mood, textures, and any notable visual elements.",
            "images": [b64],
            "stream": False,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()
