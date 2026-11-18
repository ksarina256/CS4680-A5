"""Live terminal task board — run in its own Herdr pane so the boss can watch handoffs happen."""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime

from . import engine as E

COLORS = {E.TODO: "37", E.IN_PROGRESS: "33", E.IN_REVIEW: "36", E.UNDER_REVIEW: "36",
          E.CHANGES: "31", E.DONE: "32"}
ICON = {E.TODO: "○", E.IN_PROGRESS: "◐", E.IN_REVIEW: "◔", E.UNDER_REVIEW: "◕", E.CHANGES: "↩", E.DONE: "●"}


def _c(text: str, code: str, on: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if on else text


def _ago(ts: str) -> str:
    s = int((datetime.now().astimezone() - datetime.fromisoformat(ts)).total_seconds())
    return f"{s}s ago" if s < 90 else f"{s // 60}m ago"


def render(color: bool = True) -> str:
    team, tasks = E.load_team(), E.load_tasks()
    out = [_c(f"{team.get('company', 'Company')} — task board", "1", color) +
           f"   {datetime.now().strftime('%H:%M:%S')}", ""]
    out.append(_c("AGENTS", "1;4", color))
    for role, info in team["roles"].items():
        hb = E.read_heartbeat(role)
        state = f"{hb['state']}" + (f" {hb['task']}" if hb.get("task") else "") + f" ({_ago(hb['ts'])})" if hb else "not seen yet"
        out.append(f"  {role:<12} {info.get('tool', '?'):<7} {state}")
    out += ["", _c("TASKS", "1;4", color)]
    if not tasks:
        out.append("  (no tasks yet — talk to the coordinator)")
    for t in tasks:
        st = _c(f"{ICON[t.status]} {t.status:<17}", COLORS[t.status], color)
        deps = f"  ← {','.join(t.deps)}" if t.deps else ""
        rev = f" r{t.revision}" if t.revision else "   "
        out.append(f"  {t.id:<4} {t.role:<11} {st}{rev}  {t.title[:44]}{deps}")
    done = sum(t.status == E.DONE for t in tasks)
    if tasks:
        out.append(f"\n  progress: {done}/{len(tasks)} done · revisions requested: {sum(t.revision for t in tasks)}")
    out += ["", _c("RECENT EVENTS", "1;4", color)]
    for e in E.read_events()[-8:]:
        out.append(f"  {e['ts'][11:19]}  {e['event']:<19} {e.get('task') or '':<4} {e.get('role') or ''}")
    return "\n".join(out)


def watch(interval: float = 2.0) -> None:
    color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    try:
        while True:
            print("\033[2J\033[H" + render(color), flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
