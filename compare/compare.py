#!/usr/bin/env python3
"""Compare the multi-agent team's package with the single-prompt baseline and write compare/COMPARISON.md.

    python3 compare/compare.py                          # metrics + lint only (no AI needed)
    python3 compare/compare.py --judge claude           # + blind A/B scoring by an AI judge (`claude -p`)
    python3 compare/compare.py --team runs/run1/final   # compare an archived run

What is measured (all deterministic, so you can defend them in the demo):
  * size/structure — words, headings, sections
  * grounding — source/verification labels vs. unlabeled claims, placeholders instead of invented proof
  * completeness — competitors, social posts, email, tagline
  * landing-page quality — the SAME lint checks (opc/lint.py) run on both pages
  * process — tasks, review rounds, tools used, wall-clock time
The optional judge sees both packages with randomized A/B labels so it can't tell which is which.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from opc import lint  # noqa: E402

JUDGE_CMD = {
    "claude": ["claude", "-p"],
    "codex": ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only"],
}
RUBRIC = ["accuracy", "completeness", "consistency", "clarity", "craft"]


# ------------------------------------------------------------------ loading
def load_team(final: Path) -> dict:
    mds = sorted(p for p in final.glob("T*.md"))
    html = next(iter(sorted(final.glob("*.html"))), None)
    copy = next((p for p in mds if "copywriter" in p.name), None)
    stats = json.loads((final / "stats.json").read_text()) if (final / "stats.json").exists() else {}
    return {"label": "Team", "text": "\n\n".join(p.read_text() for p in mds), "html": html,
            "copy": copy, "stats": stats}


def load_baseline(out: Path) -> dict:
    resp = out / "baseline_response.md"
    if not resp.exists():
        return {}
    html = out / "landing_page.html"
    return {"label": "Baseline", "text": resp.read_text(), "html": html if html.exists() else None,
            "copy": None, "stats": {}}


# ------------------------------------------------------------------ metrics
def count_table_rows_after(text: str, heading_pat: str) -> int:
    lines, n, heading_seen, table_seen, header_seen = text.splitlines(), 0, False, False, False
    for ln in lines:
        if not heading_seen:
            if re.search(heading_pat, ln, re.I) and ln.lstrip().startswith("#"):
                heading_seen = True
            continue
        if ln.strip().startswith("|"):
            table_seen = True
            if not header_seen:
                header_seen = True
            elif not re.fullmatch(r"[|\s:\-]+", ln.strip()):
                n += 1
        elif table_seen and ln.strip():
            break
    return n


def metrics(b: dict) -> dict:
    t = b["text"]
    text_wo_html = re.sub(r"```html.*?```", "", t, flags=re.S | re.I)
    m = {
        "words (excluding HTML)": len(text_wo_html.split()),
        "markdown headings": len(re.findall(r"^#{1,4}\s", t, re.M)),
        "sources / verification labels": len(re.findall(r"\[Verified|\[Model knowledge|https?://", t, re.I)),
        "[PLACEHOLDER] markers (honest gaps)": len(re.findall(r"\[PLACEHOLDER", t, re.I)),
        "competitors in table": count_table_rows_after(t, r"competitor"),
        "social posts": len(re.findall(r"^#{2,4}\s*post\s*#?\d", t, re.I | re.M)) or
                        len(set(re.findall(r"\bpost\s*#?([1-9])\b", t, re.I))),
        "has launch email (subject line)": bool(re.search(r"subject\s*(line)?\s*[:*]", t, re.I)),
        "has labeled primary tagline": bool(re.search(r"\*\*Primary tagline", t, re.I)),
        "has QA / verification section": bool(re.search(r"^#{1,4}\s*.*\b(QA|quality|verification)\b", t, re.I | re.M)),
    }
    if b.get("html"):
        res = lint.lint_html(b["html"], b.get("copy"))
        common = [r for r in res if "tagline" not in r[0].lower()]
        m["landing page: common lint checks passed"] = f"{sum(ok for _, ok, _ in common)}/{len(common)}"
        m["_failed"] = [n for n, ok, _ in common if not ok]
        m["_tagline"] = next((("PASS" if ok else "FAIL") for n, ok, _ in res if "tagline" in n.lower()), "n/a")
    else:
        m["landing page: common lint checks passed"] = "no HTML file found"
        m["_failed"], m["_tagline"] = ["no HTML file"], "n/a"
    s = b.get("stats") or {}
    m["tasks / agents"] = f"{s.get('tasks', 1)} tasks · {len(s.get('roles_used', [])) or 1} roles" if s else "1 prompt · 1 AI"
    m["review rounds that sent work back"] = s.get("total_revisions", 0) if s else 0
    m["AI tools used"] = ", ".join(s.get("tools_used", [])) if s else "1"
    m["wall-clock minutes"] = s.get("wall_minutes", "—") if s else "—"
    return m


# ------------------------------------------------------------------ judge
def judge(team: dict, base: dict, tool: str, limit: int = 40_000) -> dict:
    sides = [("team", team), ("baseline", base)]
    random.shuffle(sides)
    mapping = {"A": sides[0][0], "B": sides[1][0]}
    def pack(b):
        html = Path(b["html"]).read_text()[:12_000] if b.get("html") and b["label"] == "Team" else ""
        return (b["text"][:limit] + (f"\n\n[LANDING PAGE HTML]\n{html}" if html else ""))
    prompt = f"""You are a strict, impartial marketing QA lead. Two agencies answered the same brief. Score each package
1-10 on: {', '.join(RUBRIC)} (accuracy = claims grounded / nothing invented; consistency = name, tagline and CTA identical
across research, copy, landing page; craft = limits obeyed, HTML quality). Penalize fabricated statistics, testimonials or URLs.

THE BRIEF:
{(REPO / 'demo_request.md').read_text()}

=== PACKAGE A ===
{pack(sides[0][1])}

=== PACKAGE B ===
{pack(sides[1][1])}

Reply with ONLY JSON: {{"A": {{"accuracy":0,"completeness":0,"consistency":0,"clarity":0,"craft":0,"notes":"..."}},
"B": {{...same keys...}}, "winner": "A|B|tie", "reasoning": "3 sentences"}}"""
    if not shutil.which(JUDGE_CMD[tool][0]):
        raise SystemExit(f"required judge executable not found: {JUDGE_CMD[tool][0]}")
    try:
        proc = subprocess.run([*JUDGE_CMD[tool], prompt], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=900)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"{tool} judge timed out after 900s")
    (Path(__file__).parent / "judge_raw.txt").write_text(proc.stdout + "\n" + proc.stderr)
    m = re.search(r"\{.*\}", proc.stdout, re.S)
    if proc.returncode != 0 or not m:
        raise SystemExit("judge failed — see compare/judge_raw.txt")
    data = json.loads(m.group(0))
    out = {mapping[k]: data[k] for k in ("A", "B")}
    w = data.get("winner", "tie")
    out["winner"] = mapping.get(w, "tie")
    out["reasoning"] = data.get("reasoning", "")
    return out


# ------------------------------------------------------------------ report
def observations(t: dict, b: dict, j: dict | None) -> list[str]:
    o = []
    if t["landing page: common lint checks passed"] != b["landing page: common lint checks passed"]:
        o.append(f"Landing page lint (same checks on both): team **{t['landing page: common lint checks passed']}** "
                 f"vs baseline **{b['landing page: common lint checks passed']}**. "
                 f"Baseline failures: {', '.join(b['_failed']) or 'none'}.")
    o.append(f"Tagline consistency between copy pack and page (team has an explicit contract): **{t['_tagline']}**; "
             "the baseline had no separate copy artifact to check against.")
    if t["sources / verification labels"] != b["sources / verification labels"]:
        o.append(f"Grounding: team carries {t['sources / verification labels']} source/verification labels vs "
                 f"{b['sources / verification labels']} in the baseline; placeholders: {t['[PLACEHOLDER] markers (honest gaps)']} vs "
                 f"{b['[PLACEHOLDER] markers (honest gaps)']}.")
    o.append(f"The review loop sent work back **{t['review rounds that sent work back']}** time(s); the baseline had no external check.")
    o.append(f"Cost of the team: {t['tasks / agents']}, {t['wall-clock minutes']} wall-clock minutes vs one prompt. "
             "This is the honest downside — more latency, more tokens, more moving parts.")
    if j:
        o.append(f"Blind AI judge winner: **{j['winner']}** — {j['reasoning']}")
    return o


def write_report(team: dict, base: dict, tm: dict, bm: dict, j: dict | None, path: Path) -> None:
    keys = [k for k in tm if not k.startswith("_")]
    rows = "\n".join(f"| {k} | {tm[k]} | {bm.get(k, '—')} |" for k in keys)
    judge_md = ""
    if j:
        judge_md = "\n## Blind AI judge (scores 1–10, A/B order randomized)\n\n| Criterion | Team | Baseline |\n|---|---|---|\n" + \
            "\n".join(f"| {c} | {j['team'].get(c, '-')} | {j['baseline'].get(c, '-')} |" for c in RUBRIC) + \
            f"\n\nWinner: **{j['winner']}**. {j['reasoning']}\n\n- Team notes: {j['team'].get('notes', '')}\n- Baseline notes: {j['baseline'].get('notes', '')}\n"
    obs = "\n".join(f"- {x}" for x in observations(tm, bm, j))
    path.write_text(f"""# Team vs single-prompt baseline

Same request (`demo_request.md`) given to (a) the multi-agent company and (b) one AI in one prompt.

## Measured comparison

| Metric | Team (agents + review loop) | Baseline (1 prompt) |
|---|---|---|
{rows}
{judge_md}
## Auto-generated observations

{obs}

## What the team did better / worse

**Better:** The team separated research, copy, implementation, and QA into explicit handoffs. Its reviewer sent work
back {tm.get('review rounds that sent work back', 0)} time(s), and the landing page was checked with the same
deterministic linter used by the developer. The source/verification labels and explicit copy-to-page tagline contract
also make the quality claims auditable.

**Worse:** The team costs more time and setup than one prompt: it uses {tm.get('tasks / agents', 'multiple tasks')}
and depends on Herdr plus two AI CLIs. A single prompt may be sufficient for a small, low-risk deliverable.

**When I'd use which:** Use the team when the work has multiple deliverables, dependencies, or meaningful quality risk;
use the baseline for quick drafts that do not need independent review.
""")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", default=str(REPO / "workspace" / "final"))
    ap.add_argument("--baseline", default=str(REPO / "baseline" / "output"))
    ap.add_argument("--judge", choices=list(JUDGE_CMD))
    ap.add_argument("--out", default=str(Path(__file__).parent / "COMPARISON.md"))
    args = ap.parse_args()
    team, base = load_team(Path(args.team)), load_baseline(Path(args.baseline))
    if not team["text"]:
        print(f"No team deliverables in {args.team}. Run the company first (or `python3 simulate.py`).", file=sys.stderr)
        return 1
    if not base:
        print("No baseline yet. Run: python3 baseline/run_baseline.py --tool claude   (or --tool manual)", file=sys.stderr)
        return 1
    tm, bm = metrics(team), metrics(base)
    j = judge(team, base, args.judge) if args.judge else None
    write_report(team, base, tm, bm, j, Path(args.out))
    print(f"wrote {args.out}")
    for k in [k for k in tm if not k.startswith("_")]:
        print(f"  {k:<42} team={tm[k]!s:<28} baseline={bm.get(k, '—')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
