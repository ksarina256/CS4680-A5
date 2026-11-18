# Launchpad Studio — a one-person company run by AI agents

**CS4680 Prompt Engineering · Assignment 5.** You are the boss. A team of AI agents — each in its own
[Herdr](https://herdr.dev) terminal pane, mixing **Claude Code** and **Codex** — turns one request into a finished
launch package. The same request is also given to a single AI in a single prompt, and the two results are compared.

**Scenario:** a boutique launch-marketing agency. **Demo assignment** (`demo_request.md`): launch *FocusFlock*, a free
study-planner web app for college students → research brief + copy pack + landing page + QA report.

```
                       YOU (boss)
                          │  talk only to ▼
 ┌────────────────────────────────────────────────────────────────────┐
 │ Herdr workspace — one terminal pane per agent                      │
 │                                                                    │
 │  coordinator (PM, Claude) ── writes ──► workspace/tasks/Txx_*.md   │
 │                                              │ agents `wait` & claim│
 │   researcher (Codex) ─► outputs/T01 ─┐       ▼                      │
 │   copywriter (Claude) ─► outputs/T02 ─┼─► submit ─► reviewer (QA,   │
 │   developer  (Codex) ─► outputs/T03 ─┘            Claude) ──┐      │
 │        ▲                                                     │      │
 │        └──────── REVISE (numbered feedback) ◄───────────────┘      │
 │                                   approve ──► done ──► package ──► final/
 │  board pane: live task table + agent heartbeats                    │
 └────────────────────────────────────────────────────────────────────┘
```

## Assignment requirements → where they are satisfied

| Requirement | Evidence |
|---|---|
| ≥ 4 agent roles, each with an instruction file (job, inputs, outputs, quality bar) | 5 roles: `agents/coordinator.md`, `researcher.md`, `copywriter.md`, `developer.md`, `reviewer.md` (+ shared `_protocol.md`) |
| One coordinator is the only agent you talk to | `coordinator` pane; every other agent's boot prompt forbids asking the boss (`launch.py`, `_protocol.md`) |
| Herdr: every agent in its own terminal, one workspace | `launch.py` → `herdr workspace create`, `pane split`, `pane run` (1 workspace, 5 agent panes + board) |
| ≥ 2 different AI tools | `team.json`: Claude Code (coordinator, copywriter, reviewer) and Codex (researcher, developer) |
| Coordinator breaks request into a task file per role | `workspace/tasks/Txx_<role>.md`, created via `company.py new-task` (engine rejects vague briefs) |
| Agents pick up tasks, save to output folder, mark done | `company.py wait` (auto-claim) → `workspace/outputs/` → `submit` → reviewer `approve` → `done` |
| No copying between agents by hand | Only channel is the file system + `company.py`; the engine passes upstream paths and reviewer feedback automatically |
| Reviewer role; work sent back and improved ≥ once | `agents/reviewer.md`; engine policy `min_revisions: 1` (`team.json`) → every deliverable is sent back at least once; evidence in `workspace/final/reviews/*_round1.md` |
| Baseline: same request, single AI, one prompt | `baseline/run_baseline.py` (+ saved `baseline/output/PROMPT_USED.md`) |
| Compare and explain team better/worse | `compare/compare.py` → `compare/COMPARISON.md` (measured table + blind AI judge + your analysis) |
| Prompt-engineering techniques | `docs/PROMPT_ENGINEERING.md` (15 techniques mapped to files) |

## Setup

The runtime is stdlib-only; no project packages need to be installed. For the live assignment demo, download or
install these external tools and log in to both AI CLIs:

1. **Python 3.10+** (Python 3.11 is recommended; verify with `python3 --version`).
2. **Herdr** — on macOS, `brew install herdr`. Start `herdr` once in a separate terminal so its local server is
   running before you run `python3 launch.py`. Optional integrations improve pane-state detection:
   `herdr integration install claude` and `herdr integration install codex`.
3. **Claude Code** — install it using Anthropic's current official instructions, then verify `claude --version`.
4. **Codex CLI** — install it using OpenAI's current official instructions, then verify `codex --version`.

The checked-in `team.json` uses current interactive Codex flags (workspace-write, automatic approval, and live search)
so worker panes can keep their `wait` loops alive. The baseline uses `codex exec --ephemeral` for one response. If a
future CLI changes a flag, run `codex --help` or `codex exec --help` and update the corresponding command.

From VS Code, open this folder as the workspace, install the recommended Python extensions when prompted, select your
Python 3.10+ interpreter, and run the included **Run unit tests** task. The `.vscode/` files provide test, simulation,
and Herdr dry-run tasks.

If you want an isolated interpreter, create the one referenced by the VS Code settings:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

There are no packages to install into it.

Before downloading any AI tools, these two checks work offline and require only Python:

```bash
python3 -m unittest discover -s tests -v
python3 simulate.py
```

## Run it for real

```bash
python3 launch.py            # builds the Herdr workspace and starts all agents (add --dry-run to preview)
```
1. Click the **coordinator** pane and paste the contents of `demo_request.md` (or your own request).
   (`python3 launch.py --auto-request` tries to type it for you.)
2. Watch the **board** pane: tasks appear, specialists claim them, the reviewer sends work back, everything ends `● done`.
3. The coordinator runs `package` and writes `workspace/final/FINAL_REPORT.md`. Open `workspace/final/T03_developer.html`.
4. Keep the evidence in git: `python3 company.py archive run1` → `runs/run1/` (tasks, outputs, reviews, event log, final).

### Baseline + comparison
```bash
python3 baseline/run_baseline.py --tool claude     # one prompt, one AI  (or --tool codex / --tool manual)
python3 compare/compare.py --judge claude          # metrics + lint + blind A/B judge → compare/COMPARISON.md
python3 compare/compare.py --team runs/run1/final  # compare an archived run
```
`compare.py` writes a ready-to-review explanation; personalize it with the concrete review files and observations from
your run before submitting. A baseline response is deliberately not fabricated by the offline simulator: run the
one-prompt command (or save a manual one-AI reply to `baseline/output/baseline_response.md`) before running `compare.py`.

## How the engine works (`opc/engine.py`)

- **Task file** = markdown with front-matter (`id, role, status, depends_on, output, revision…`) + brief + acceptance criteria + history.
- **Statuses:** `todo → in_progress → in_review → under_review → done`, or `→ changes_requested → in_progress …` after a `revise`.
- **Handoff:** `wait --role X` blocks, atomically claims the next ready task for X (dependencies must be *approved*), and prints the
  brief plus upstream file paths and any reviewer feedback. `submit` validates the deliverable exists and moves it to review.
- **Review loop:** reviewer `review T02 --verdict revise|approve --score N --notes-file …`. Policy in `team.json`:
  first drafts must be sent back (`min_revisions`), after `max_revisions` the reviewer must approve with caveats.
- **Quality gates in code:** vague briefs rejected; empty deliverables rejected; `lint-html` checks the landing page.
- **Observability:** `logs/events.jsonl`, per-agent heartbeats, `company.py board --watch`, `package` → `final/MANIFEST.md` + `stats.json`.

## Make it your own

Everything is data-driven: edit `team.json` to swap an agent's tool (`"tool": "codex"` ↔ `"claude"`), rename roles, or change
policy; edit `demo_request.md` for a different assignment; edit `agents/*.md` to change behavior. Other scenario ideas that fit
the same roles: tutoring company (curriculum + lesson copy + site), game studio (design doc + story + prototype page), travel agency.

## Troubleshooting

- **herdr flag errors:** `launch.py` prints the failing command; run `herdr --help` / `herdr pane --help` and adjust
  `Launcher` in `launch.py`. `--dry-run` shows exactly what it will run, and you can always create panes by hand
  (`ctrl+b` then `v`/`-` to split) and paste the lines from the dry run.
- **Agents ask permission constantly:** adjust the `tools` commands in `team.json` (Claude Code uses
  `--permission-mode acceptEdits`; Codex uses `--approve-for-me`) or `.claude/settings.json`; flags can differ
  by CLI version.
- **An agent seems idle:** that's normal — it is in its `wait` loop (≤ 60 s per call). The board shows heartbeats.
- **An agent stopped looping** (LLM CLIs sometimes end their turn): click its pane and type `continue your work loop: run python3 company.py wait --role <role>`.
- **Researcher can't browse (Codex sandbox):** that's fine; it must label claims `[Model knowledge — verify]`.
- **Start over:** `python3 company.py init --reset` (clears `workspace/`).

## Repo map

```
team.json            roles → tool, instruction file; policy
launch.py            Herdr workspace builder        simulate.py   offline scripted dry run
company.py + opc/    task engine, CLI, board, linter
agents/              role cards + shared protocol   templates/    task brief template
demo_request.md      the boss's assignment          baseline/     single-prompt baseline
compare/             team vs baseline report        docs/         prompt-eng. map, demo script, rubric traceability
tests/               unit + end-to-end tests        workspace/    runtime state (tasks, outputs, reviews, final)
runs/                archived run evidence
```
