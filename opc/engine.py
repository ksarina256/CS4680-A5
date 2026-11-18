"""File-based task engine for the one-person company (stdlib only).

Agents never talk to each other directly. The coordinator writes task files,
specialists pick them up with `wait`, save deliverables under workspace/outputs,
and `submit` them. The reviewer `review`s each deliverable; work is sent back
with `revise` and re-queued for its author until it is approved (status: done).

    todo -> in_progress -> in_review -> under_review -> done
                 ^                            |
                 +---- changes_requested <----+   (verdict: revise)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent

TODO, IN_PROGRESS, IN_REVIEW, UNDER_REVIEW, CHANGES, DONE = (
    "todo", "in_progress", "in_review", "under_review", "changes_requested", "done",
)
STATUSES = [TODO, IN_PROGRESS, IN_REVIEW, UNDER_REVIEW, CHANGES, DONE]
DIRS = ["tasks", "outputs", "reviews", "drafts", "logs/agents", "final"]
DEFAULT_POLICY = {
    "dependency_gate": "approved",   # "approved" (dep is done) or "submitted" (dep is in review)
    "min_revisions": 1,              # every deliverable must be sent back at least this many times
    "max_revisions": 2,              # after this many, reviewer must approve (with caveats)
    "min_output_bytes": 200,
}


class OPCError(Exception):
    """A user-facing error (bad command, policy violation, missing file)."""


# --------------------------------------------------------------------------- paths / config
def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def home() -> Path:
    """Runtime state directory (tasks, outputs, reviews, logs, final)."""
    return Path(os.environ.get("COMPANY_HOME") or REPO / "workspace")


def load_team() -> dict:
    path = Path(os.environ.get("COMPANY_TEAM") or REPO / "team.json")
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        raise OPCError(f"team config not found: {path}")


def policy() -> dict:
    return {**DEFAULT_POLICY, **load_team().get("policy", {})}


def role_info(role: str) -> dict:
    roles = load_team()["roles"]
    if role not in roles:
        raise OPCError(f"unknown role '{role}'. Valid roles: {', '.join(roles)}")
    return roles[role]


def ensure_dirs() -> None:
    for d in DIRS:
        (home() / d).mkdir(parents=True, exist_ok=True)


def init(reset: bool = False) -> None:
    h = home()
    if reset and h.exists():
        for child in h.iterdir():
            if child.name == ".gitkeep":
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    ensure_dirs()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@contextmanager
def lock(timeout: float = 15.0):
    """Cross-process mutex (mkdir is atomic everywhere). Stale locks expire after 30s."""
    home().mkdir(parents=True, exist_ok=True)
    d = home() / ".lock"
    start = time.time()
    while True:
        try:
            d.mkdir()
            break
        except FileExistsError:
            try:
                if time.time() - d.stat().st_mtime > 30:
                    shutil.rmtree(d, ignore_errors=True)
                    continue
            except FileNotFoundError:
                continue
            if time.time() - start > timeout:
                raise OPCError("could not acquire workspace lock (delete workspace/.lock if stuck)")
            time.sleep(0.05)
    try:
        yield
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------- events / heartbeats
def log_event(event: str, task: Optional[str] = None, role: Optional[str] = None, **extra) -> None:
    rec = {"ts": now(), "event": event, "task": task, "role": role, **extra}
    path = home() / "logs" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def read_events() -> list[dict]:
    path = home() / "logs" / "events.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def heartbeat(role: str, state: str, task: Optional[str] = None) -> None:
    rec = {"role": role, "state": state, "task": task, "ts": now()}
    atomic_write(home() / "logs" / "agents" / f"{role}.json", json.dumps(rec))


def read_heartbeat(role: str) -> Optional[dict]:
    p = home() / "logs" / "agents" / f"{role}.json"
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# --------------------------------------------------------------------------- task files
KEY_ORDER = ["id", "title", "role", "status", "depends_on", "output", "revision",
             "review_file", "scores", "created_by", "created_at", "updated_at"]
_FM = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.S)


def parse_task_text(text: str) -> tuple[dict, str]:
    m = _FM.match(text)
    if not m:
        raise OPCError("task file is missing its --- front matter ---")
    meta = {}
    for line in m.group(1).splitlines():
        if line.strip() and not line.startswith("#"):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def render_task_text(meta: dict, body: str) -> str:
    keys = [k for k in KEY_ORDER if k in meta] + [k for k in meta if k not in KEY_ORDER]
    head = "\n".join(f"{k}: {meta[k]}" for k in keys)
    return f"---\n{head}\n---\n{body.lstrip(chr(10))}"


@dataclass
class Task:
    path: Path
    meta: dict
    body: str

    id = property(lambda s: s.meta["id"])
    title = property(lambda s: s.meta.get("title", ""))
    role = property(lambda s: s.meta["role"])
    status = property(lambda s: s.meta.get("status", TODO))
    revision = property(lambda s: int(s.meta.get("revision") or 0))
    deps = property(lambda s: [d.strip() for d in s.meta.get("depends_on", "").split(",") if d.strip()])

    def save(self) -> None:
        self.meta["updated_at"] = now()
        atomic_write(self.path, render_task_text(self.meta, self.body))

    def add_history(self, msg: str) -> None:
        if "## History" not in self.body:
            self.body = self.body.rstrip() + "\n\n## History\n"
        self.body = self.body.rstrip("\n") + f"\n- {now()} — {msg}\n"

    def output_path(self) -> Path:
        return home() / self.meta["output"]


def load_tasks() -> list[Task]:
    d = home() / "tasks"
    tasks = []
    for p in sorted(d.glob("*.md")) if d.exists() else []:
        meta, body = parse_task_text(p.read_text())
        tasks.append(Task(p, meta, body))
    return sorted(tasks, key=lambda t: t.id)


def get_task(task_id: str) -> Task:
    for t in load_tasks():
        if t.id.lower() == task_id.lower():
            return t
    raise OPCError(f"no such task: {task_id}")


def set_status(t: Task, new: str, role: str, note: str = "", event: Optional[str] = None) -> None:
    old = t.status
    t.meta["status"] = new
    t.add_history(f"{old} → {new} by {role}" + (f" — {note}" if note else ""))
    t.save()
    log_event(event or new, t.id, role, from_status=old, to_status=new, note=note)


def check_body(body: str) -> None:
    """Engine-enforced quality bar for the coordinator's task briefs."""
    if len(body.strip()) < 200:
        raise OPCError("task body is too thin (<200 chars). Give context, inputs, deliverable format.")
    if not re.search(r"acceptance criteria", body, re.I):
        raise OPCError("task body must contain an 'Acceptance criteria' section")
    bullets = re.findall(r"^\s*(?:[-*]|\d+[.)])\s+\S", body, re.M)
    if len(bullets) < 3:
        raise OPCError("task body needs at least 3 bullet points (acceptance criteria / inputs)")


def new_task(role: str, title: str, body: str, deps: Optional[list[str]] = None,
             output: Optional[str] = None, task_id: Optional[str] = None,
             created_by: str = "coordinator") -> Task:
    info = role_info(role)
    if info.get("kind") == "coordinator":
        raise OPCError("tasks cannot be assigned to the coordinator")
    check_body(body)
    deps = [d.strip() for d in (deps or []) if d.strip()]
    with lock():
        existing = load_tasks()
        ids = {t.id for t in existing}
        if task_id is None:
            nums = [int(m.group(1)) for t in existing if (m := re.match(r"T(\d+)$", t.id))]
            task_id = f"T{(max(nums) + 1) if nums else 1:02d}"
        if task_id in ids:
            raise OPCError(f"task id already exists: {task_id}")
        missing = [d for d in deps if d not in ids]
        if missing:
            raise OPCError(f"unknown dependencies: {', '.join(missing)} (create them first)")
        output = output or f"outputs/{task_id}_{role}.{info.get('ext', 'md')}"
        parts = Path(output).parts
        if Path(output).is_absolute() or ".." in parts or not parts or parts[0] != "outputs":
            raise OPCError("output path must be relative and inside outputs/")
        ts = now()
        meta = {"id": task_id, "title": title, "role": role, "status": TODO,
                "depends_on": ", ".join(deps), "output": output, "revision": "0",
                "created_by": created_by, "created_at": ts, "updated_at": ts}
        ensure_dirs()
        t = Task(home() / "tasks" / f"{task_id}_{role}.md", meta, body)
        t.add_history(f"created by {created_by}")
        t.save()
        log_event("created", task_id, created_by, assignee=role, title=title, depends_on=deps)
    heartbeat(created_by, "planning", task_id)
    return t


# --------------------------------------------------------------------------- queueing
@dataclass
class Assignment:
    kind: str   # WORK | REWORK | REVIEW | QA
    task: Task


def _deps_met(t: Task, by_id: dict[str, Task]) -> bool:
    ok = {DONE} if policy()["dependency_gate"] == "approved" else {IN_REVIEW, UNDER_REVIEW, DONE}
    return all(d in by_id and by_id[d].status in ok for d in t.deps)


def _find_assignment(role: str) -> Optional[Assignment]:
    info = role_info(role)
    tasks = load_tasks()
    by_id = {t.id: t for t in tasks}
    if info.get("kind") == "reviewer":
        for t in tasks:                       # pending reviews come first
            if t.status == IN_REVIEW:
                return Assignment("REVIEW", t)
    mine = [t for t in tasks if t.role == role and t.status in (TODO, CHANGES) and _deps_met(t, by_id)]
    mine.sort(key=lambda t: (t.status != CHANGES, t.id))  # finish rework before new work
    if not mine:
        return None
    t = mine[0]
    if t.status == CHANGES:
        return Assignment("REWORK", t)
    return Assignment("QA" if info.get("kind") == "reviewer" else "WORK", t)


def wait(role: str, timeout: float = 60, poll: float = 2.0) -> Optional[Assignment]:
    """Block until `role` has something to do, claim it atomically, return it (None on timeout)."""
    role_info(role)
    deadline = time.time() + timeout
    heartbeat(role, "waiting")
    while True:
        with lock():
            found = _find_assignment(role)
            if found:
                if found.kind == "REVIEW":
                    set_status(found.task, UNDER_REVIEW, role, "picked up for review", "review_started")
                    heartbeat(role, "reviewing", found.task.id)
                else:
                    set_status(found.task, IN_PROGRESS, role, f"picked up ({found.kind})", "picked_up")
                    heartbeat(role, "working", found.task.id)
                return found
        if time.time() >= deadline:
            return None
        time.sleep(poll)


def submit(task_id: str, role: Optional[str] = None, note: str = "") -> Task:
    with lock():
        t = get_task(task_id)
        if role and t.role != role:
            raise OPCError(f"{task_id} belongs to '{t.role}', not '{role}'")
        if t.status != IN_PROGRESS:
            raise OPCError(f"{task_id} is '{t.status}'; only in_progress tasks can be submitted "
                           f"(did you run `wait` first?)")
        out = t.output_path()
        if not out.exists():
            raise OPCError(f"deliverable not found: {out}. Save it there first.")
        if out.stat().st_size < policy()["min_output_bytes"]:
            raise OPCError(f"deliverable {out.name} is almost empty ({out.stat().st_size} bytes)")
        if role_info(t.role).get("kind") == "reviewer":     # reviewer-owned task (final QA)
            set_status(t, DONE, t.role, note or "completed", "completed")
        else:
            set_status(t, IN_REVIEW, t.role, note or "submitted for review", "submitted")
    heartbeat(t.role, "idle", t.id)
    return t


def review(task_id: str, verdict: str, notes: str, role: Optional[str] = None,
           score: Optional[int] = None) -> Task:
    if verdict not in ("approve", "revise"):
        raise OPCError("verdict must be 'approve' or 'revise'")
    if not role:
        raise OPCError("a reviewer role is required (set COMPANY_ROLE or pass --role reviewer)")
    if role_info(role).get("kind") != "reviewer":
        raise OPCError(f"role '{role}' is not a reviewer")
    if score is not None and (not isinstance(score, int) or not 0 <= score <= 10):
        raise OPCError("score must be an integer from 0 to 10")
    if len(notes.strip()) < 40:
        raise OPCError("review notes are too short; give specific, actionable feedback")
    pol = policy()
    with lock():
        t = get_task(task_id)
        if t.status not in (IN_REVIEW, UNDER_REVIEW):
            raise OPCError(f"{task_id} is '{t.status}', not awaiting review")
        rnd = t.revision + 1
        if verdict == "approve" and t.revision < pol["min_revisions"]:
            raise OPCError(
                f"POLICY: round {rnd} drafts must be sent back (min_revisions={pol['min_revisions']}). "
                f"Find at least 3 concrete improvements and use --verdict revise.")
        if verdict == "revise" and t.revision >= pol["max_revisions"]:
            raise OPCError(
                f"POLICY: max_revisions={pol['max_revisions']} reached. Approve with caveats and "
                f"list remaining issues in the notes.")
        rf = home() / "reviews" / f"{t.id}_round{rnd}.md"
        header = (f"# Review of {t.id} — {t.title}\n\n- Round: {rnd}\n- Verdict: **{verdict.upper()}**\n"
                  f"- Score: {score if score is not None else 'n/a'}/10\n- Reviewer: {role or 'reviewer'}\n"
                  f"- Time: {now()}\n\n---\n\n")
        atomic_write(rf, header + notes.strip() + "\n")
        t.meta["review_file"] = f"reviews/{rf.name}"
        if score is not None:
            t.meta["scores"] = ",".join(filter(None, [t.meta.get("scores", ""), str(score)]))
        if verdict == "revise":
            t.meta["revision"] = str(t.revision + 1)
            set_status(t, CHANGES, role or "reviewer", f"sent back (round {rnd}, score {score})", "revision_requested")
        else:
            set_status(t, DONE, role or "reviewer", f"approved (round {rnd}, score {score})", "approved")
    if role:
        heartbeat(role, "idle", task_id)
    return t


def format_assignment(a: Assignment, role: str) -> str:
    t, h = a.task, home()
    rel = lambda p: os.path.relpath(p)  # noqa: E731
    out = ["=" * 72, f"ASSIGNMENT: {a.kind}   task {t.id}   (round {t.revision + 1})", "=" * 72,
           t.path.read_text().rstrip(), ""]
    req = h / "request.md"
    if req.exists():
        out.append(f"Boss's original request: {rel(req)}")
    if a.kind in ("WORK", "REWORK", "QA") and t.deps:
        out.append("Upstream deliverables (approved inputs): " +
                   ", ".join(rel(get_task(d).output_path()) for d in t.deps))
    if a.kind == "REWORK" and t.meta.get("review_file"):
        rf = h / t.meta["review_file"]
        out += ["", "-" * 72, f"REVIEWER FEEDBACK you must address ({rel(rf)}):", "-" * 72, rf.read_text().rstrip()]
    if a.kind == "REVIEW":
        out += ["", f"Deliverable to review: {rel(t.output_path())}"]
        if t.deps:
            out.append("Upstream inputs to cross-check: " +
                       ", ".join(rel(get_task(d).output_path()) for d in t.deps))
        prev = sorted((h / "reviews").glob(f"{t.id}_round*.md"))
        if prev:
            out += ["", "Your previous review(s) — verify every point was fixed: " + ", ".join(rel(p) for p in prev)]
    out += ["", "NEXT STEPS", "-" * 10]
    if a.kind in ("WORK", "REWORK", "QA"):
        out += [f"1. Save the deliverable to {rel(t.output_path())} (overwrite when reworking).",
                "2. Self-check against your role card's quality bar and every acceptance criterion.",
                f'3. Run: python3 company.py submit {t.id} --note "one-line summary"',
                f"4. Run: python3 company.py wait --role {role}   (next assignment)"]
    else:
        draft = rel(h / "reviews" / f"_draft_{t.id}.md")
        out += ["1. Read the deliverable and its upstream inputs. Score it with your rubric.",
                f"2. Write your review notes to {draft} (template in your role card).",
                f"3. Run: python3 company.py review {t.id} --verdict approve|revise --score N --notes-file {draft}",
                f"4. Run: python3 company.py wait --role {role}   (next assignment)"]
    return "\n".join(out)


def wait_all(timeout: float = 60, poll: float = 2.0, on_change=None) -> bool:
    """Coordinator helper: block until every task is done (True) or timeout (False)."""
    deadline, last = time.time() + timeout, None
    while True:
        tasks = load_tasks()
        snap = tuple((t.id, t.status, t.revision) for t in tasks)
        if snap != last and on_change:
            on_change(tasks)
        last = snap
        if tasks and all(t.status == DONE for t in tasks):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(poll)


# --------------------------------------------------------------------------- request / package / stats
def save_request(text: str) -> Path:
    ensure_dirs()
    p = home() / "request.md"
    atomic_write(p, text.strip() + "\n")
    log_event("request_saved", role="coordinator", chars=len(text))
    return p


def _minutes(a: Optional[str], b: Optional[str]) -> Optional[float]:
    if not a or not b:
        return None
    return round((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 60, 2)


def compute_stats() -> dict:
    tasks, events, team = load_tasks(), read_events(), load_team()
    per = []
    for t in tasks:
        evs = [e for e in events if e.get("task") == t.id]
        created = next((e["ts"] for e in evs if e["event"] == "created"), None)
        finished = next((e["ts"] for e in reversed(evs) if e["event"] in ("approved", "completed")), None)
        per.append({"id": t.id, "title": t.title, "role": t.role,
                    "tool": team["roles"].get(t.role, {}).get("tool"), "status": t.status,
                    "revisions": t.revision, "scores": t.meta.get("scores", ""),
                    "minutes_to_done": _minutes(created, finished)})
    stamps = [e["ts"] for e in events]
    return {"company": team.get("company"), "tasks": len(tasks),
            "tasks_done": sum(t.status == DONE for t in tasks),
            "total_revisions": sum(t.revision for t in tasks),
            "review_events": sum(e["event"] in ("approved", "revision_requested") for e in events),
            "tools_used": sorted({p["tool"] for p in per if p["tool"]}),
            "roles_used": sorted({t.role for t in tasks}),
            "wall_minutes": _minutes(min(stamps), max(stamps)) if stamps else None,
            "per_task": per}


def package() -> dict:
    tasks = load_tasks()
    if not tasks:
        raise OPCError("no tasks exist yet")
    pending = [f"{t.id}({t.status})" for t in tasks if t.status != DONE]
    if pending:
        raise OPCError("cannot package yet; not done: " + ", ".join(pending))
    missing = [f"{t.id}: {t.output_path()}" for t in tasks if not t.output_path().is_file()]
    if missing:
        raise OPCError("cannot package; deliverable file(s) missing: " + ", ".join(missing))
    final = home() / "final"
    final.mkdir(parents=True, exist_ok=True)
    for t in tasks:
        shutil.copy2(t.output_path(), final / t.output_path().name)
    rv = final / "reviews"
    rv.mkdir(exist_ok=True)
    for p in (home() / "reviews").glob("*.md"):
        if not p.name.startswith("_draft_"):
            shutil.copy2(p, rv / p.name)
    stats = compute_stats()
    atomic_write(final / "stats.json", json.dumps(stats, indent=2))
    rows = "\n".join(
        f"| {p['id']} | {p['role']} | {p['tool']} | {p['revisions']} | {p['scores'] or '-'} | "
        f"{p['minutes_to_done'] if p['minutes_to_done'] is not None else '-'} | {p['title']} |"
        for p in stats["per_task"])
    atomic_write(final / "MANIFEST.md",
                 f"# Delivery manifest — {stats['company']}\n\n"
                 f"- Tasks: {stats['tasks_done']}/{stats['tasks']} done\n"
                 f"- Review rounds that sent work back: {stats['total_revisions']}\n"
                 f"- AI tools used: {', '.join(stats['tools_used'])}\n"
                 f"- Wall-clock minutes: {stats['wall_minutes']}\n\n"
                 f"| Task | Role | Tool | Revisions | Scores | Minutes | Title |\n|---|---|---|---|---|---|---|\n{rows}\n")
    log_event("packaged", role="coordinator", files=[p.name for p in final.iterdir()])
    return stats


def archive(name: str) -> Path:
    if not re.fullmatch(r"[\w.-]+", name):
        raise OPCError("archive name may only contain letters, digits, _ . -")
    dest = REPO / "runs" / name
    if dest.exists():
        raise OPCError(f"{dest} already exists")
    shutil.copytree(home(), dest, ignore=shutil.ignore_patterns(".lock", "*.tmp"))
    return dest
