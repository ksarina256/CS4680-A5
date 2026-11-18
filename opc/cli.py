"""Command-line interface: `python3 company.py <command>` — the only way agents touch shared state."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import board, engine as E, lint


def _role(args) -> str | None:
    return getattr(args, "role", None) or os.environ.get("COMPANY_ROLE")


def _read_text(args, file_attr="body_file", text_attr="body") -> str:
    if getattr(args, file_attr, None):
        return Path(getattr(args, file_attr)).read_text()
    if getattr(args, text_attr, None):
        return getattr(args, text_attr)
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise E.OPCError("provide text via --body-file, --body, or stdin")


def cmd_init(a):
    E.init(reset=a.reset)
    print(f"workspace ready: {E.home()}" + (" (reset)" if a.reset else ""))


def cmd_save_request(a):
    p = E.save_request(_read_text(a, "file", "text"))
    print(f"saved boss request to {os.path.relpath(p)}")


def cmd_new_task(a):
    t = E.new_task(a.role, a.title, _read_text(a), a.depends_on.split(",") if a.depends_on else [],
                   a.output, a.id, created_by=os.environ.get("COMPANY_ROLE") or "coordinator")
    print(f"created {t.id} for {t.role}: {t.title}\n  deliverable: {os.path.relpath(t.output_path())}"
          f"\n  depends on: {', '.join(t.deps) or '—'}")


def cmd_list(a):
    tasks = [t for t in E.load_tasks() if (not a.role or t.role == a.role) and (not a.status or t.status == a.status)]
    if a.json:
        print(json.dumps([{**t.meta} for t in tasks], indent=2))
    else:
        for t in tasks:
            print(f"{t.id}  {t.role:<11} {t.status:<18} rev={t.revision}  {t.title}")


def cmd_show(a):
    print(E.get_task(a.id).path.read_text())


def cmd_wait(a):
    role = _role(a)
    if not role:
        raise E.OPCError("--role is required (or set COMPANY_ROLE)")
    found = E.wait(role, a.timeout, a.poll)
    if not found:
        print(f"NO_TASK_YET for '{role}'. Nothing is wrong — run the same `wait` command again.")
    else:
        print(E.format_assignment(found, role))


def cmd_submit(a):
    t = E.submit(a.id, _role(a), a.note or "")
    print(f"{t.id} -> {t.status}." + (" Waiting for the reviewer." if t.status == E.IN_REVIEW else " Done."))
    print(f"Next: python3 company.py wait --role {t.role}")


def cmd_review(a):
    notes = Path(a.notes_file).read_text() if a.notes_file else (a.notes or "")
    t = E.review(a.id, a.verdict, notes, _role(a), a.score)
    print(f"{t.id} -> {t.status}" + (f" (sent back; revision {t.revision})" if t.status == E.CHANGES else " (approved)"))
    print(f"Next: python3 company.py wait --role {_role(a) or 'reviewer'}")


def cmd_board(a):
    if a.watch:
        board.watch(a.interval)
    else:
        print(board.render(sys.stdout.isatty() and not os.environ.get("NO_COLOR")))


def cmd_wait_all(a):
    def show(tasks):
        print(" | ".join(f"{t.id}:{t.status}" + (f"(r{t.revision})" if t.revision else "") for t in tasks), flush=True)
    if E.wait_all(a.timeout, a.poll, show):
        print("ALL_DONE — run `python3 company.py package`, then write the final report.")
    else:
        print("STILL_RUNNING — agents are working. Run `wait-all` again (do NOT do their work).")


def cmd_package(a):
    s = E.package()
    print(f"packaged {s['tasks_done']}/{s['tasks']} tasks into {os.path.relpath(E.home() / 'final')} "
          f"(revisions: {s['total_revisions']}, tools: {', '.join(s['tools_used'])})")


def cmd_stats(a):
    print(json.dumps(E.compute_stats(), indent=2))


def cmd_archive(a):
    print(f"archived run to {os.path.relpath(E.archive(a.name))}")


def cmd_lint(a):
    res = lint.lint_html(Path(a.file), Path(a.copy) if a.copy else None)
    print(lint.format_results(res))
    sys.exit(0 if all(ok for _, ok, _ in res) else 1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="company.py", description="One-Person Company task engine")
    s = p.add_subparsers(dest="cmd", required=True)

    x = s.add_parser("init", help="create workspace folders"); x.add_argument("--reset", action="store_true"); x.set_defaults(f=cmd_init)
    x = s.add_parser("save-request", help="coordinator: store the boss's request verbatim")
    x.add_argument("--file"); x.add_argument("--text"); x.set_defaults(f=cmd_save_request)

    x = s.add_parser("new-task", help="coordinator: create a task file for a role")
    x.add_argument("--role", required=True); x.add_argument("--title", required=True)
    x.add_argument("--depends-on", default=""); x.add_argument("--output"); x.add_argument("--id")
    x.add_argument("--body-file"); x.add_argument("--body"); x.set_defaults(f=cmd_new_task)

    x = s.add_parser("list"); x.add_argument("--role"); x.add_argument("--status"); x.add_argument("--json", action="store_true"); x.set_defaults(f=cmd_list)
    x = s.add_parser("show"); x.add_argument("id"); x.set_defaults(f=cmd_show)

    x = s.add_parser("wait", help="block until you have an assignment (auto-claims it)")
    x.add_argument("--role"); x.add_argument("--timeout", type=float, default=60); x.add_argument("--poll", type=float, default=2); x.set_defaults(f=cmd_wait)
    x = s.add_parser("submit", help="hand your deliverable over for review"); x.add_argument("id"); x.add_argument("--role"); x.add_argument("--note"); x.set_defaults(f=cmd_submit)
    x = s.add_parser("review", help="reviewer: approve or send work back")
    x.add_argument("id"); x.add_argument("--role"); x.add_argument("--verdict", required=True, choices=["approve", "revise"])
    x.add_argument("--score", type=int); x.add_argument("--notes"); x.add_argument("--notes-file"); x.set_defaults(f=cmd_review)

    x = s.add_parser("board"); x.add_argument("--watch", action="store_true"); x.add_argument("--interval", type=float, default=2); x.set_defaults(f=cmd_board)
    x = s.add_parser("wait-all", help="coordinator: block until all tasks are done")
    x.add_argument("--timeout", type=float, default=60); x.add_argument("--poll", type=float, default=2); x.set_defaults(f=cmd_wait_all)
    x = s.add_parser("package", help="coordinator: collect approved deliverables into workspace/final"); x.set_defaults(f=cmd_package)
    x = s.add_parser("stats"); x.set_defaults(f=cmd_stats)
    x = s.add_parser("archive", help="copy the whole workspace to runs/<name> to commit as evidence"); x.add_argument("name"); x.set_defaults(f=cmd_archive)
    x = s.add_parser("lint-html", help="check the landing page against the quality bar")
    x.add_argument("file"); x.add_argument("--copy", help="copy-pack file to verify tagline consistency"); x.set_defaults(f=cmd_lint)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.f(args)
    except E.OPCError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2
    return 0
