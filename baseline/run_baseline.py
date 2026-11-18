#!/usr/bin/env python3
"""Baseline: give the SAME request to ONE AI in ONE prompt (no roles, no tasks, no review loop).

    python3 baseline/run_baseline.py --tool agy        # uses `agy -p`
    python3 baseline/run_baseline.py --tool codex      # uses `codex exec`
    python3 baseline/run_baseline.py --tool manual     # prints the prompt; paste it into any chat UI yourself,
                                                       # then save the reply to baseline/output/baseline_response.md and run with --extract

Fairness: the prompt is the boss's request (demo_request.md) plus ONE paragraph telling the AI to deliver all
four items in a single reply. Nothing else — no extra hints, no role play, no second pass.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "baseline" / "output"

SUFFIX = """

You get exactly one reply, so put the entire launch package in it, in this order: (1) research brief,
(2) copy pack, (3) the landing page as ONE complete self-contained HTML file inside a ```html code fence,
(4) a QA report. Do not ask questions."""

TOOLS = {
    # Put -p last because it consumes the next argument as the prompt.
    "agy": ["agy", "--sandbox", "-p"],
    # Keep the baseline runnable from a downloaded folder that has not been git-initialized yet.
    "codex": ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only"],
}


def build_prompt() -> str:
    return (REPO / "demo_request.md").read_text().strip() + SUFFIX


def extract_html(text: str) -> str | None:
    m = re.search(r"```html\s*\n(.*?)```", text, re.S | re.I)
    return m.group(1).strip() if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tool", choices=[*TOOLS, "manual"], default="agy")
    ap.add_argument("--extract", action="store_true",
                    help="skip running anything; just extract the HTML from an existing baseline_response.md")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    response = OUT / "baseline_response.md"
    prompt = build_prompt()
    (OUT / "PROMPT_USED.md").write_text(prompt + "\n")

    if not args.extract:
        if args.tool == "manual":
            print(prompt)
            print(f"\n--- Paste the prompt above into ONE chat with ONE AI. Save its full reply to\n    {response}\n"
                  f"    then run: python3 baseline/run_baseline.py --extract ---")
            return 0
        if not shutil.which(TOOLS[args.tool][0]):
            print(f"required executable not found: {TOOLS[args.tool][0]}. Install it or use --tool manual.",
                  file=sys.stderr)
            return 2
        try:
            proc = subprocess.run([*TOOLS[args.tool], prompt], capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f"{args.tool} timed out after {args.timeout}s", file=sys.stderr)
            return 124
        if proc.returncode != 0:
            print(proc.stderr, file=sys.stderr)
            return proc.returncode
        response.write_text(proc.stdout)

    if not response.exists():
        print(f"no response file at {response}", file=sys.stderr)
        return 1
    text = response.read_text()
    html = extract_html(text)
    if html:
        (OUT / "landing_page.html").write_text(html + "\n")
    print(f"saved {response} ({len(text.split())} words)"
          + (f" and {OUT / 'landing_page.html'}" if html else " — WARNING: no ```html block found"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
