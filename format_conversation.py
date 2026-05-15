#!/usr/bin/env python3
"""Read output/history.json and write output/conversation.md."""

import json
import os
import sys

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")
MILESTONES = set(int(x) for x in os.environ.get("MILESTONES", "1,5,10,20,50").split(","))

history_path = os.path.join(OUTPUT_DIR, "history.json")
out_path = os.path.join(OUTPUT_DIR, "conversation.md")

if not os.path.exists(history_path):
    print(f"Not found: {history_path}", file=sys.stderr)
    sys.exit(1)

open(out_path, "w").close()

with open(history_path) as f:
    history = json.load(f)

with open(out_path, "w") as f:
    f.write("# Aesthetic Loop — Conversation Log\n\n")
    f.write(f"*{len(history)} iterations recorded.*\n\n")

    f.write("## Table of Contents\n\n")
    for entry in history:
        n = entry["iter"]
        star = "★ " if n in MILESTONES else ""
        anchor = f"iteration-{n}"
        f.write(f"- [{star}Iteration {n}](#{anchor})\n")
    f.write("\n---\n\n")

    for entry in history:
        n = entry["iter"]
        image_file = os.path.basename(entry["image"])

        f.write(f"## Iteration {n}\n\n")
        f.write(f"**Bob → Charly**\n\n{entry['prompt']}\n\n")
        f.write(f"![iter_{n:04d}]({image_file})\n\n")
        f.write(f"**Dylan** *(describing the image)*\n\n{entry['description']}\n\n")
        f.write(f"**Alice → Bob**\n\n{entry['critique']}\n\n")
        f.write("---\n\n")

print(f"Written {len(history)} iterations to {out_path}")
