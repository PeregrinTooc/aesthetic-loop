import json
import os
import tempfile
from datetime import datetime

from agents import Alice, Bob
from tools import describe_image, paint_image

INITIAL_PROMPT = os.environ.get("INITIAL_PROMPT", "a mountain landscape at golden hour, photorealistic, cinematic lighting")
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "50"))
MILESTONES = set(int(x) for x in os.environ.get("MILESTONES", "1,5,10,20,50").split(","))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/output")

HISTORY_PATH = os.path.join(OUTPUT_DIR, "history.json")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def save_history(history: list) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(history, f, indent=2)
    os.replace(tmp, HISTORY_PATH)


def main() -> None:
    bob = Bob()
    alice = Alice()

    current_prompt = INITIAL_PROMPT
    last_critique = ""
    history = []

    log(f"Starting aesthetic loop — {MAX_ITERATIONS} iterations")
    log(f"Initial prompt: {current_prompt}")

    for iter_num in range(1, MAX_ITERATIONS + 1):
        log(f"=== Iteration {iter_num}/{MAX_ITERATIONS} ===")

        log("Bob is thinking...")
        prompt = bob.think(current_prompt, last_critique)
        log(f"Bob's prompt: {prompt}")

        log("Charly is painting...")
        image_path = paint_image(prompt, iter_num)

        log("Dylan is describing...")
        description = describe_image(image_path)
        log(f"Dylan's description: {description[:120]}...")

        log("Alice is critiquing...")
        critique = alice.critique(description)
        log(f"Alice's critique:\n{critique}")

        entry = {
            "iter": iter_num,
            "prompt": prompt,
            "image": image_path,
            "description": description,
            "critique": critique,
        }
        history.append(entry)
        save_history(history)

        if iter_num in MILESTONES:
            log(f"*** MILESTONE {iter_num} ***")

        current_prompt = prompt
        last_critique = critique

    log("Loop complete.")


if __name__ == "__main__":
    main()
