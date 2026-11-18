# 1–2 minute demo video — shot list

Record your screen with the Herdr workspace visible (all panes + board). Rehearse once; the first run of agents is the slow part,
so consider recording the real run and speeding up the waiting parts (say so on screen: "sped up 8×").

| Time | On screen | Say (≈) |
|---|---|---|
| 0:00–0:10 | Terminal: `python3 launch.py` → Herdr workspace appears with 6 panes | "I'm the boss of Launchpad Studio — a one-person company. Five AI agents, each in its own Herdr pane: PM and copywriter and editor on Claude Code, researcher and developer on Codex." |
| 0:10–0:20 | Paste `demo_request.md` into the **coordinator** pane | "I only ever talk to the coordinator." |
| 0:20–0:35 | Coordinator writes `plan.md`, creates T01–T04; board pane fills with tasks and dependencies | "It plans, then writes a task file per role. Agents pick tasks up on their own — no copy-paste between them." |
| 0:35–0:55 | Researcher works → submit → reviewer pane lights up → **revision requested** (show review file with numbered fixes) | "The QA editor reviews every deliverable. Here it sent the research back with specific fixes; the researcher reworks it." |
| 0:55–1:10 | Board shows T01 ● done → copywriter/developer start; `lint-html` PASS in developer pane | "Dependencies gate the work, and the developer verifies its page with a deterministic linter." |
| 1:10–1:25 | `ALL_DONE` → coordinator's final report; open `workspace/final/T03_developer.html` in a browser | "Package assembled with a manifest of review rounds and scores." |
| 1:25–1:50 | Show `compare/COMPARISON.md` table (team vs baseline) | "Same request to a single prompt: it shipped N lint failures and unlabeled claims; the team caught them through review. Cost: more time and tokens." |

Tips: increase terminal font size; close other panes' scrollback noise with `clear`; keep the board pane visible the whole time.
