# Assignment 5 rubric traceability

This checklist maps the assignment handout to the code and the artifacts a grader can inspect. The video is a
separate submission requirement; this file covers the implementation evidence that the video should demonstrate.

## Required implementation evidence

| Handout requirement | Evidence in this project | What to show in the demo |
|---|---|---|
| At least four roles, each with job, inputs, outputs, and quality bar | `agents/coordinator.md`, `agents/researcher.md`, `agents/copywriter.md`, `agents/developer.md`, `agents/reviewer.md` | Open the role cards and point to the required sections. |
| One coordinator is the only agent the boss talks to | `agents/_protocol.md`, `agents/coordinator.md`, and `launch.py` boot prompts | Paste the request only into the coordinator pane. |
| Herdr, one terminal per agent, one workspace, two AI tools | `launch.py` creates one Herdr workspace, five agent panes, and one board pane; `team.json` assigns Claude and Codex | Run `python3 launch.py --dry-run`, then show the live six-pane workspace. |
| Coordinator creates a task file per role | `company.py new-task`, `workspace/tasks/Txx_<role>.md`, and the coordinator card | Show task files and their dependency graph on the board. |
| Agents hand off through files and finish tasks | `opc/engine.py` status machine, `workspace/outputs/`, and `company.py submit` | Show an output path in an assignment and a task moving to review/done. |
| No hand-copying between agents | `opc/engine.py format_assignment()` passes upstream file paths; no agent-to-agent chat API exists | Point out that downstream agents receive paths, not pasted content. |
| Reviewer checks work and sends it back at least once | `team.json` review policy (`min_revisions: 1`), `workspace/reviews/*_round1.md`, and `company.py review` | Show a round-1 `REVISE`, rework, and later approval. |
| Same request given to one AI as a baseline | `baseline/run_baseline.py`, `baseline/output/PROMPT_USED.md`, and the response saved after the one-prompt run | Show that the prompt contains the original request plus one instruction paragraph. |
| Compare and explain team vs. baseline | `compare/compare.py` and `compare/COMPARISON.md` | Show the measured table and the better/worse analysis. |

## Prompt-engineering evidence

`docs/PROMPT_ENGINEERING.md` names and locates 15 techniques used in the role cards, task engine, linter,
review loop, and baseline. The most visible techniques are role prompting, explicit contracts, measurable quality
bars, few-shot examples, negative constraints, grounded claims, rubric-based review, iterative refinement, and
deterministic verification.

## Grading-criteria checklist

- Scenario and relevance: the demo request defines FocusFlock, college-student audience, launch timing, budget, and tone.
- Team design and implementation: roles, Herdr launcher, two tools, task engine, status board, and file handoffs are all present.
- Prompt engineering: the technique map and role cards provide concrete, inspectable examples rather than generic prompts.
- Final deliverable: the packaged research brief, copy pack, self-contained landing page, and QA report live under `workspace/final/` after `package`.
- Presentation/live demo: follow `docs/DEMO_SCRIPT.md`; submit the separate 1–2 minute video link and repository link through the course form.

## Local verification commands

```bash
python3 -m unittest discover -s tests -v
python3 simulate.py
python3 launch.py --dry-run
```

The simulation is an offline proof of the workflow; the checked-in `runs/offline-validation/` archive preserves its
task graph, outputs, review rounds, event log, and final package. A live Herdr run is still required for the assignment demonstration.
