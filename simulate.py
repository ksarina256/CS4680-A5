#!/usr/bin/env python3
"""Offline dry run: scripted "agents" (threads) exercise the real engine end to end.

No AI tools or Herdr needed. It proves the handoff + review loop works and is used by the tests.
    python3 simulate.py            # runs in ./workspace_sim and prints the final board
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opc import board, engine as E  # noqa: E402

TAGLINE = "Plan less. Focus more."
BODY = """## Context
Simulated task for {role}. {extra}

## Inputs
- workspace/request.md
- upstream deliverables listed in the assignment

## Deliverable
- A file saved at the output path

## Acceptance criteria
- Meets the quality bar in the role card
- Contains no unverifiable claims
- Is consistent with upstream deliverables
"""


def make_output(role: str, t: E.Task) -> str:
    """Return a deterministic but rubric-shaped deliverable for the offline demo."""
    rnd = t.revision + 1
    revision_note = ("\n\n> Revision note: addressed the reviewer's opening, grounding, and consistency points."
                     if rnd > 1 else "")
    if role == "developer":
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FocusFlock | Plan less. Focus more.</title>
  <style>
    :root { color-scheme: light; --ink: #17202a; --paper: #fffaf0; --sky: #dff3f2; --coral: #e96b5f; --line: #c8d9d8; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: system-ui, sans-serif; color: var(--ink); background: var(--paper); line-height: 1.55; }
    a { color: inherit; }
    .skip-link { position: absolute; left: -9999px; }
    .skip-link:focus { left: 1rem; top: 1rem; background: var(--paper); padding: .5rem; }
    header, main, footer { max-width: 70rem; margin: auto; padding: 1.25rem; }
    header { display: flex; justify-content: space-between; align-items: center; }
    nav a { margin-left: 1rem; font-weight: 700; }
    .hero { display: grid; grid-template-columns: 1.2fr .8fr; gap: 2rem; align-items: center; padding: 5rem 1.25rem; }
    .eyebrow { color: #8b3b34; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
    h1 { max-width: 11ch; font-size: clamp(3rem, 8vw, 6rem); line-height: .98; margin: .4rem 0 1rem; }
    h2 { font-size: clamp(1.8rem, 4vw, 3rem); }
    .subhead { max-width: 34rem; font-size: 1.2rem; }
    .cta { display: inline-block; border: 0; border-radius: 999px; background: var(--coral); color: white; padding: .8rem 1.15rem; font: inherit; font-weight: 800; text-decoration: none; cursor: pointer; }
    .cta:focus-visible, a:focus-visible, input:focus-visible, summary:focus-visible { outline: 3px solid #1b6e70; outline-offset: 3px; }
    .flock-card { min-height: 16rem; border: 2px solid var(--line); border-radius: 2rem; background: var(--sky); padding: 2rem; display: grid; place-items: center; font-size: 5rem; }
    .features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
    .feature, .signup { border: 1px solid var(--line); border-radius: 1.25rem; padding: 1.25rem; background: white; }
    .faq { max-width: 48rem; }
    details { border-top: 1px solid var(--line); padding: 1rem 0; }
    summary { cursor: pointer; font-weight: 800; }
    .signup { margin: 3rem 0; background: var(--sky); }
    form { display: flex; gap: .75rem; flex-wrap: wrap; align-items: end; }
    label { display: grid; gap: .35rem; font-weight: 700; }
    input { min-width: min(100%, 20rem); padding: .75rem; border: 1px solid var(--line); border-radius: .6rem; font: inherit; }
    footer { border-top: 1px solid var(--line); }
    @media (max-width: 700px) { header { align-items: flex-start; } nav a { margin-left: .5rem; } .hero { grid-template-columns: 1fr; padding-top: 3rem; } .features { grid-template-columns: 1fr; } form { display: grid; } .cta { width: 100%; text-align: center; } }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; } }
  </style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header><a href="#main" aria-label="FocusFlock home"><strong>FocusFlock</strong></a><nav aria-label="Main navigation"><a href="#features">Features</a><a href="#faq">FAQ</a></nav></header>
  <main id="main">
    <section class="hero" aria-labelledby="hero-title">
      <div><p class="eyebrow">A calmer study plan</p><h1 id="hero-title">Plan less. Focus more.</h1><p class="subhead">Class deadlines and a focus timer in one friendly place, so your next study session is easier to start.</p><a class="cta" href="#signup">Join the flock</a></div>
      <div class="flock-card" aria-label="An illustrated flock of birds">🐦 🐦 🐦</div>
    </section>
    <section id="features" aria-labelledby="features-title"><h2 id="features-title">Your study plan, in one place.</h2><div class="features"><article class="feature"><h3>See deadlines</h3><p>Keep class due dates visible before they become a late-night surprise.</p></article><article class="feature"><h3>Start a focus session</h3><p>Use a pomodoro-style timer to give one small study block a clear beginning and end.</p></article><article class="feature"><h3>Grow your flock</h3><p>Stay focused and watch your friendly birds grow with your progress.</p></article></div></section>
    <section id="faq" class="faq" aria-labelledby="faq-title"><h2 id="faq-title">Questions, answered.</h2><details><summary>What is FocusFlock?</summary><p>A free web app for combining class deadlines with pomodoro-style study sessions.</p></details><details><summary>Is it free?</summary><p>Yes. FocusFlock is planned as a free app with organic launch channels.</p></details><details><summary>Do I need a perfect schedule?</summary><p>No. Start with the next deadline and one focused session.</p></details></section>
    <section id="signup" class="signup" aria-labelledby="signup-title"><h2 id="signup-title">Ready when you are.</h2><p>Get the launch note when FocusFlock is ready.</p><form action="#"><label for="email">School email<input id="email" name="email" type="email" autocomplete="email" required></label><button class="cta" type="submit">Join the flock</button></form></section>
  </main>
  <footer><p>FocusFlock: a little more focus for your next study session.</p></footer>
</body>
</html>
"""
    if role == "copywriter":
        return ("""# Copy pack: FocusFlock
## Voice guide
Warm, clear, lightly witty. We say “your next study session” / we never say “crush your goals”; we say “one focused block” / we never say “hustle harder”; we say “friendly flock” / we never say “gamified productivity hack”.
**Primary tagline:** Plan less. Focus more.
**Secondary taglines:** Deadlines, gathered. Focus, started. | Your next study session, in one place. | A calmer way to begin.
## Value propositions
- **See the next deadline:** Class due dates stay visible before they become a late-night surprise.
- **Start one focused block:** A pomodoro-style timer gives studying a clear beginning and end.
- **Let focus grow:** Your friendly flock grows as you stay focused.
## Landing page copy
### Hero
H1 = Plan less. Focus more. Subhead = Class deadlines and a focus timer in one friendly place, so your next study session is easier to start. CTA = Join the flock.
### Features
- **See deadlines:** Keep class due dates visible before they become a late-night surprise.
- **Start a focus session:** Use a pomodoro-style timer to give one small study block a clear beginning and end.
- **Grow your flock:** Stay focused and watch your friendly birds grow with your progress.
### Social proof
[PLACEHOLDER: student quote to be collected before launch]
### FAQ
Q: What is FocusFlock? A: A free web app for combining class deadlines with pomodoro-style study sessions.
Q: Is it free? A: Yes. FocusFlock is planned as a free app with organic launch channels.
Q: Do I need a perfect schedule? A: No. Start with the next deadline and one focused session.
### Footer line
FocusFlock: a little more focus for your next study session.
## Social posts
### Post 1 — Instagram
Copy: Your syllabus has three deadlines this week. Put the next one somewhere you can actually see it. FocusFlock helps you start one focused block. Link in bio. Hashtags: #college #studytips. Visual: three deadline cards becoming one tidy list. Character count: 159.
### Post 2 — TikTok
Copy: POV: you opened your calendar and found the deadline before the deadline found you. FocusFlock pairs class dates with a focus timer. Hashtags: #studytok #college. Visual: a calm before-and-after desk reset. Character count: 142.
### Post 3 — X
Copy: A study plan does not need to be perfect. It needs a next deadline, one focused block, and maybe a tiny bird. Meet FocusFlock. Hashtags: #studentlife. Visual: timer beside a class deadline. Character count: 126.
### Post 4 — LinkedIn
Copy: For students balancing lectures, labs, and life: FocusFlock brings class deadlines and a pomodoro-style focus session together. Hashtags: #highered #students. Visual: simple weekly study view. Character count: 133.
### Post 5 — Instagram
Copy: Start with the next thing, not the whole semester. FocusFlock helps you see a deadline, start a session, and grow your flock. Hashtags: #studygram #college. Visual: one bird joining a small flock. Character count: 132.
## Launch email
Subject: A calmer way to start studying
Preview text: FocusFlock puts your next deadline and focus session together.
Body: Studying gets harder when your deadlines live in one place and your focus timer lives in another. FocusFlock brings them together in one friendly web app, so you can see what is next and start one focused block. Stay focused and your flock grows with you. Join the flock when launch arrives.
CTA: Join the flock
""" + revision_note)
    if role == "researcher":
        return ("""# Research brief: FocusFlock
## 1. Executive summary
FocusFlock is for undergraduates whose study plans are scattered across syllabi, calendars, and timer apps. [Model knowledge — verify] The opportunity is not another generic productivity dashboard: it is a free, friendly place that connects the next class deadline to one focused session. Position it as “the calm starting point for college study,” with a small flock as a progress cue rather than pressure. [Model knowledge — verify]
## 2. Target audience
### The deadline juggler
Situation: several classes have overlapping due dates and the student decides what to study only when urgency peaks. [Model knowledge — verify] Needs: one visible next deadline, a short starting ritual, and a simple way to see progress. Frustrations: scattered course systems, unclear priorities, and guilt after an unplanned evening. Hangs out: campus group chats, course Discords, YouTube study channels, and student subreddits. [Model knowledge — verify]
### The timer user
Situation: the student already tries pomodoro sessions but has to keep a second place for class deadlines. [Model knowledge — verify] Needs: a low-friction timer, a visible connection to coursework, and a gentle reason to return. Frustrations: timer-only apps feel disconnected from school, notifications interrupt, and streak language can feel judgmental. Hangs out: TikTok study creators, Instagram study accounts, and campus libraries. [Model knowledge — verify]
### The overloaded starter
Situation: the hardest part is beginning a task when the semester feels like one giant list. [Model knowledge — verify] Needs: a small next action, friendly language, and a free tool with no setup burden. Frustrations: complex templates, paid tiers, and productivity hype. Hangs out: orientation groups, peer tutoring channels, and student organization newsletters. [Model knowledge — verify]
## 3. Competitor landscape
| Competitor | What it does | Price | Strength | Gap we can own |
|---|---|---|---|---|
| Google Calendar | Calendar events and reminders | Free [Model knowledge — verify] | Familiar and widely available [Model knowledge — verify] | It can hold deadlines, but FocusFlock can make the next study session feel like the natural next step. [Model knowledge — verify] |
| Notion Calendar | Calendar connected to workspace pages | Free tier / unknown paid details [Model knowledge — verify] | Flexible organization [Model knowledge — verify] | Flexibility can mean setup work; FocusFlock can be intentionally narrow for starting a study block. [Model knowledge — verify] |
| Forest | Focus timer with a growing tree | Paid or tiered pricing varies by platform [Model knowledge — verify] | Memorable focus ritual [Model knowledge — verify] | A timer-and-tree loop does not necessarily show class deadlines; FocusFlock connects both in one flow. [Model knowledge — verify] |
| Todoist | Task lists, projects, and reminders | Free tier / paid plans [Model knowledge — verify] | Mature task capture [Model knowledge — verify] | General task management can feel like another inbox; FocusFlock can center the student’s next class deadline and session. [Model knowledge — verify] |
| MyStudyLife | Student planner for schedules and assignments | Free tier / paid features may vary [Model knowledge — verify] | Student-specific planning | Planning breadth can add complexity; FocusFlock can own the friendly first five minutes of studying. [Model knowledge — verify] |
## 4. Positioning recommendation
Positioning: For undergraduates who know what is due but struggle to begin, FocusFlock is the free study planner that turns the next class deadline into one calm focus session, with a friendly flock that grows as you stay focused. Differentiators: deadline-to-session connection; intentionally small, non-hustle starting ritual; progress represented as a friendly flock rather than a public score. Why us, why now: the launch can meet students in organic study communities with a specific promise and no paid acquisition. [Model knowledge — verify]
## 5. Messaging guardrails
DO: say “start with the next deadline” because it is concrete; say “one focused block” because it lowers the starting bar; say “friendly flock” because it makes progress visible without hype; say “free” only while the product plan supports it; say “in one place” because the core value is connection. [Model knowledge — verify]
DON’T: promise better grades because there is no evidence; don’t use “crush,” “grind,” or “hustle” because the brief asks for friendly, non-cringe language; don’t imply a verified student community before collecting proof; don’t call it an AI tutor because that is outside the product brief; don’t claim automatic course integration unless it ships. [Model knowledge — verify]
## 6. Sources & confidence
This offline demonstration uses model-knowledge labels rather than live browsing. Every competitor description, price, and audience observation above is [Model knowledge — verify]. Before launch, verify each price and feature on the competitor’s current product page.
## 7. Open questions
Verify which deadline-import workflow ships in three weeks, whether the bird progression is saved between sessions, what “free” includes, and which campus communities allow organic launch posts. Collect permissioned student feedback before replacing the social-proof placeholder.
""" + revision_note)
    return """# QA report
## Requirement traceability
| Requirement | Evidence | Status |
|---|---|---|
| Research brief | T01 includes personas, five competitors, positioning, guardrails, labels, and open questions. | ✅ |
| Copy pack | T02 contains one tagline, value propositions, landing copy, five social posts, and one email. | ✅ |
| Landing page | T03 is one self-contained semantic HTML file with responsive CSS, accessible form controls, FAQ details, and the approved tagline. | ✅ |
| Review loop | T01–T03 each received round-1 revision feedback and a later approval. | ✅ |
## Cross-deliverable consistency
Product name: FocusFlock. Primary tagline: Plan less. Focus more. CTA: Join the flock. Unsupported proof remains a placeholder or is labelled for verification. ✅
## Review loop summary
T01, T02, and T03 each completed one revision; reviewer feedback addressed grounding, opening clarity, and cross-file consistency. T04 completed the final package check.
## Remaining risks
Verify competitor prices, collect permissioned student proof, and confirm the final deadline-import workflow before launch.
## Ship recommendation
Ready for a live demo and internal review; ship publicly after the remaining verification items are closed.
"""


def worker(role: str, stop: threading.Event, speed: float, say) -> None:
    while not stop.is_set():
        a = E.wait(role, timeout=1, poll=0.1)
        if a is None:
            continue
        t = a.task
        say(f"{role:<10} picked up {t.id} ({a.kind})")
        time.sleep(speed)
        if a.kind == "REVIEW":
            if t.revision == 0:
                E.review(t.id, "revise", "1) Tighten the opening. 2) Cite a source for each claim. "
                         "3) Align names with upstream deliverables.", role, 6)
                say(f"{role:<10} sent {t.id} BACK for revision")
            else:
                E.review(t.id, "approve", "All previous points addressed; ready to ship. No remaining issues.", role, 9)
                say(f"{role:<10} approved {t.id}")
        else:
            t.output_path().parent.mkdir(parents=True, exist_ok=True)
            t.output_path().write_text(make_output(t.role, t))
            E.submit(t.id, role, note=f"simulated {a.kind.lower()}")
            say(f"{role:<10} submitted {t.id}")


def run(home: Path, speed: float = 0.2, quiet: bool = False) -> dict:
    os.environ["COMPANY_HOME"] = str(home)
    say = (lambda *_: None) if quiet else (lambda m: print("  " + m, flush=True))
    E.init(reset=True)
    E.save_request("Simulated boss request: launch FocusFlock.")
    say("coordinator creating tasks")
    E.new_task("researcher", "Audience & competitor research", BODY.format(role="researcher", extra=""))
    E.new_task("copywriter", "Launch copy pack", BODY.format(role="copywriter", extra=""), ["T01"])
    E.new_task("developer", "Landing page", BODY.format(role="developer", extra=""), ["T01", "T02"])
    E.new_task("reviewer", "Final QA cross-check", BODY.format(role="reviewer", extra=""), ["T01", "T02", "T03"])
    stop = threading.Event()
    threads = [threading.Thread(target=worker, args=(r, stop, speed, say), daemon=True)
               for r in ("researcher", "copywriter", "developer", "reviewer")]
    for th in threads:
        th.start()
    ok = E.wait_all(timeout=60, poll=0.1)
    stop.set()
    for th in threads:
        th.join(timeout=3)
    if not ok:
        raise SystemExit("simulation timed out")
    stats = E.package()
    E.atomic_write(E.home() / "plan.md", """# Offline demo plan

Objective: exercise the FocusFlock launch workflow without external AI tools.

Task graph: T01 research → T02 copy → T03 landing page → T04 final QA.

Definition of done: every task is approved, each producer completes at least one review revision, the HTML linter passes, and the package contains a manifest plus review evidence.
""")
    E.atomic_write(E.home() / "final" / "FINAL_REPORT.md", """# Final report

## Request

Offline validation of the FocusFlock launch workflow.

## What we delivered

| File | What it is |
|---|---|
| T01_researcher.md | Audience, competitor, and positioning brief |
| T02_copywriter.md | Launch copy pack |
| T03_developer.html | Self-contained landing page |
| T04_reviewer.md | Whole-package QA report |

## How the review loop improved the work

The scripted reviewer sent T01, T02, and T03 back once each. Round-1 review files and round-2 approvals are preserved under `final/reviews/`.

## Assumptions & open issues

This is an offline engine demonstration, not a substitute for a live Herdr run. Research claims remain labelled for verification.

## Next steps for the boss

Run the live launcher after installing Herdr and both AI CLIs; then run the real baseline and comparison before recording the demo.
""")
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", default=str(Path(__file__).resolve().parent / "workspace_sim"))
    ap.add_argument("--speed", type=float, default=0.3)
    args = ap.parse_args()
    stats = run(Path(args.home), args.speed)
    print("\n" + board.render(color=sys.stdout.isatty()))
    print(f"\nSimulation OK: {stats['tasks_done']}/{stats['tasks']} tasks done, "
          f"{stats['total_revisions']} revisions, output in {args.home}/final")
