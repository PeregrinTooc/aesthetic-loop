#!/usr/bin/env python3
"""Read output/history.json and write output/conversation.md.

If the loop is complete (last iteration == MAX_ITERATIONS), also export a PDF
via weasyprint. Install with: pip install weasyprint markdown2
"""

import json
import os
import sys

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")
MILESTONES = set(int(x) for x in os.environ.get("MILESTONES", "1,5,10,20,50").split(","))
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "50"))

history_path = os.path.join(OUTPUT_DIR, "history.json")
out_path = os.path.join(OUTPUT_DIR, "conversation.md")
pdf_path = os.path.join(OUTPUT_DIR, "conversation.pdf")

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

last_iter = history[-1]["iter"] if history else 0
if last_iter < MAX_ITERATIONS:
    print(f"Loop not complete ({last_iter}/{MAX_ITERATIONS}), skipping PDF export.")
    sys.exit(0)

try:
    import markdown2
    from weasyprint import HTML, CSS
except ImportError:
    print("PDF export requires weasyprint and markdown2: pip install weasyprint markdown2", file=sys.stderr)
    sys.exit(1)

with open(out_path) as f:
    md_text = f.read()

html_body = markdown2.markdown(md_text, extras=["fenced-code-blocks", "tables"])

# Resolve image paths relative to the output directory so WeasyPrint finds them.
base_url = f"file://{os.path.abspath(OUTPUT_DIR)}/"

html = f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 860px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #111; }}
  h1, h2, h3 {{ font-family: 'Helvetica Neue', Arial, sans-serif; }}
  h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-top: 2em; }}
  img {{ max-width: 100%; height: auto; display: block; margin: 1em 0; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 2em 0; }}
  ul {{ line-height: 2; }}
</style>
</head><body>{html_body}</body></html>"""

HTML(string=html, base_url=base_url).write_pdf(pdf_path)
print(f"PDF exported to {pdf_path}")
