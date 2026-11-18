# Prompt-engineering techniques used (and where to find them)

| # | Technique | Where it is used | Why it helps |
|---|---|---|---|
| 1 | **Role / persona prompting** | `Identity` section of every card in `agents/` | Sets expertise, attitude and voice (skeptical researcher, demanding editor) so outputs differ in kind, not just topic. |
| 2 | **Explicit input → output contracts** | `Inputs` / `Outputs` in each card; `templates/task_body.md` | Downstream agents can rely on verbatim headings (e.g. `**Primary tagline:**`), so handoffs need no human glue. |
| 3 | **Task decomposition / plan-then-act** | `agents/coordinator.md` step 3 (`workspace/plan.md` before any task) | Forces the PM to reason about dependencies before delegating (chain-of-thought externalised as an artifact). |
| 4 | **Measurable quality bars** | `Quality bar` in each card; `engine.check_body` rejects vague briefs | "≥ 4 competitors each with price + gap" is checkable; "good research" is not. |
| 5 | **Few-shot examples (good vs bad)** | `Worked example` in every card | Shows the target quality and the failure mode (generic hype copy, vague review comments). |
| 6 | **Rubric-based critique (LLM-as-judge)** | `agents/reviewer.md` rubric, overall = *lowest* criterion; `compare/compare.py --judge` (blind A/B) | Structured scoring is more consistent than free-form opinions; min-score prevents averaging away defects. |
| 7 | **Reflection / self-consistency check** | `Self-check` checklist in every card, run *before* `submit` | Cheap first-pass error catching before the reviewer's time is spent. |
| 8 | **Iterative refinement loop** | review → `changes_requested` → REWORK with numbered feedback → re-review; engine-enforced `min_revisions` | Models improve markedly when given specific critique; the policy guarantees at least one cycle. |
| 9 | **Grounding & hallucination control** | Researcher labels (`[Verified: url]` / `[Model knowledge — verify]`); Copywriter `[PLACEHOLDER]` for proof | Makes uncertainty visible and bans invented stats/testimonials. |
| 10 | **Negative constraints ("Never")** | `Never` section in each card | Prevents role bleed (copywriter writing HTML, coordinator doing research, reviewer rewriting). |
| 11 | **Tool-use / ReAct-style loop** | `agents/_protocol.md` work loop (`wait` → act → `submit`) | Agents act through a small, safe CLI; every action has observable feedback (`ERROR:` messages explain policy). |
| 12 | **Deterministic verification tools** | `python3 company.py lint-html` (developer + reviewer) | Replaces opinion with a machine check for objective requirements (a11y, no external assets, tagline present). |
| 13 | **Structured, delimited formats** | Task files with front-matter + headed sections; review template; fenced output templates | Reduces parsing ambiguity for both agents and scripts. |
| 14 | **Heterogeneous models** | `team.json`: Antigravity *and* Codex across roles | Different model families have different blind spots; mixing reduces correlated errors. |
| 15 | **Controlled baseline (ablation)** | `baseline/run_baseline.py` — same request, one prompt | Isolates what the team structure (not just the model) adds. |
