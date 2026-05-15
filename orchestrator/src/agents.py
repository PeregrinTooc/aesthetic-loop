import os

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
BOB_MODEL = os.environ.get("BOB_MODEL", "gemma3:12b")
ALICE_MODEL = os.environ.get("ALICE_MODEL", "mistral-small3.1:latest")

BOB_SYSTEM = """\
You are Bob, an art director working with a Stable Diffusion image generator.
Your job is to write and refine text-to-image prompts.

Rules:
- Output ONLY the prompt text. No preamble, no explanation, no quotes.
- Prompts should be comma-separated descriptive phrases: subject, style, lighting, mood, technical qualities.
- Absorb Alice's critique and make targeted changes. Do not start from scratch unless she says so.
- Keep prompts under 200 words.\
"""

ALICE_SYSTEM = """\
You are Alice, an aesthetic critic evaluating AI-generated images.
You receive a detailed description of an image (written by Dylan, a vision model) and must critique it.

Structure your response in exactly three parts:
WORKS: [what is visually successful — be specific]
CHANGE: [what is weak, off, or missing — be specific]
DIRECTION: [one concrete, actionable instruction for Bob to improve the next image]

Be direct. Avoid vague praise. Your direction must be something Bob can act on in a prompt.\
"""


def _chat(model: str, system: str, user_message: str) -> str:
    resp = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


class Bob:
    def think(self, current_prompt: str, critique: str) -> str:
        if critique:
            user_msg = (
                f"Current prompt:\n{current_prompt}\n\n"
                f"Alice's critique:\n{critique}\n\n"
                "Rewrite or refine the prompt based on her direction."
            )
        else:
            user_msg = (
                f"Starting prompt:\n{current_prompt}\n\n"
                "Polish this into a strong Stable Diffusion prompt."
            )
        return _chat(BOB_MODEL, BOB_SYSTEM, user_msg)


class Alice:
    def critique(self, description: str) -> str:
        user_msg = f"Image description:\n{description}"
        return _chat(ALICE_MODEL, ALICE_SYSTEM, user_msg)
