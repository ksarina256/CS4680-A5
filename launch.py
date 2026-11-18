#!/usr/bin/env python3
"""Launch the whole company inside ONE Herdr workspace — one terminal pane per agent.

    python3 launch.py                 # build the workspace and start every agent
    python3 launch.py --dry-run       # print the herdr commands without running them
    python3 launch.py --auto-request  # also type demo_request.md into the coordinator pane (best effort)

Layout (each box is a real terminal pane running an AI CLI or the board):

    +-----------------+-----------------+
    | coordinator     | researcher      | antigravity | codex
    | (you talk here) +-----------------+
    +-----------------+ copywriter      | antigravity
    | reviewer        +-----------------+
    +-----------------+ developer       |   codex
    | task board      |                 |
    +-----------------+-----------------+

Roles, tools and instruction files all come from team.json, so swapping an agent between
Antigravity and Codex is a one-word change.
"""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
from opc import engine  # noqa: E402


def boot_prompt(role: str, info: dict, company: str) -> str:
    base = (f"You are the {info['title']} (role id: {role}) at {company}, a one-person company: a human boss "
            f"plus a team of AI agents that collaborate ONLY through files and `python3 company.py`. "
            f"First read agents/_protocol.md and {info['instructions']} completely. ")
    if info.get("kind") == "coordinator":
        return base + ("Then greet the boss in one short line and wait for their request. You are the only "
                       "agent the boss talks to.")
    return base + (f"Then immediately start your work loop: run `python3 company.py wait --role {role}` and "
                   f"keep repeating it forever. Never ask the boss questions; only the coordinator does that.")


class Launcher:
    def __init__(self, dry_run: bool = False, root: Path = REPO):
        self.dry, self.root, self.calls, self._n = dry_run, root, [], 1
        self.team = engine.load_team()

    # -- herdr plumbing -----------------------------------------------------------------
    def herdr(self, *args: str, check: bool = True) -> dict:
        cmd = ["herdr", *args]
        self.calls.append(cmd)
        if self.dry:
            print("$ " + shlex.join(cmd))
            self._n += 1
            return {"result": {"root_pane": {"pane_id": "1-1"}, "pane": {"pane_id": f"1-{self._n}"}}}
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            if check:
                raise SystemExit(f"herdr failed: {shlex.join(cmd)}\n{proc.stderr or proc.stdout}\n"
                                 "Tip: run `herdr --help` — flags can differ between versions.")
            return {}
        try:
            return json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def pane_id(resp: dict, key: str) -> str:
        obj = resp.get("result", {}).get(key) or {}
        pid = obj.get("pane_id") or obj.get("id")
        if not pid:
            raise SystemExit(f"could not read '{key}.pane_id' from herdr response: {resp}")
        return pid

    # -- commands that go into each pane --------------------------------------------------
    def agent_command(self, role: str) -> str:
        info = self.team["roles"][role]
        tool = self.team["tools"][info["tool"]]["command"]
        prompt = boot_prompt(role, info, self.team["company"])
        return f"cd {shlex.quote(str(self.root))} && env COMPANY_ROLE={role} {tool} {shlex.quote(prompt)}"

    def board_command(self) -> str:
        return f"cd {shlex.quote(str(self.root))} && python3 company.py board --watch"

    # -- main flow ----------------------------------------------------------------------
    def launch(self, auto_request: bool = False, request_delay: float = 15.0) -> dict[str, str]:
        roles = self.team["roles"]
        coord = next(r for r, i in roles.items() if i["kind"] == "coordinator")
        reviewers = [r for r, i in roles.items() if i["kind"] == "reviewer"]
        producers = [r for r, i in roles.items() if i["kind"] == "producer"]

        missing: list[str] = []
        for tool in sorted({i["tool"] for i in roles.values()}):
            command = shlex.split(self.team["tools"][tool]["command"])
            if not command:
                raise SystemExit(f"tool '{tool}' has an empty command in team.json")
            exe = command[0]
            if not self.dry and not shutil.which(exe):
                missing.append(f"{tool} ('{exe}')")
        if missing:
            raise SystemExit(
                "Missing required AI CLI(s): " + ", ".join(missing) + ". "
                "Install/log in to each tool, then verify it with `<command> --version`."
            )
        if not self.dry and not shutil.which("herdr"):
            raise SystemExit("herdr is not installed or not on PATH (see README → Setup).")
        if not self.dry:
            server_status = subprocess.run(["herdr", "status", "server"], capture_output=True, text=True)
            status_text = (server_status.stdout + server_status.stderr).lower()
            if server_status.returncode == 0 and "not running" in status_text:
                raise SystemExit(
                    "Herdr is installed but its server is not running. Start `herdr` in a separate terminal "
                    "to launch/attach the Herdr workspace, then run this command again."
                )

        missing_instructions = [
            f"{role}: {info['instructions']}"
            for role, info in roles.items()
            if not (self.root / info["instructions"]).exists()
        ]
        if missing_instructions:
            raise SystemExit("Missing role instruction file(s): " + ", ".join(missing_instructions))

        engine.init()
        ws = self.herdr("workspace", "create", "--cwd", str(self.root), "--label", self.team["workspace_label"])
        panes: dict[str, str] = {coord: self.pane_id(ws, "root_pane")}

        prev = panes[coord]
        for i, role in enumerate(producers):          # right-hand column
            side = ("--direction", "right") if i == 0 else ("--direction", "down")
            target = panes[coord] if i == 0 else prev
            prev = panes[role] = self.pane_id(self.herdr("pane", "split", target, *side, "--no-focus"), "pane")
        below = panes[coord]
        for role in reviewers:                        # under the coordinator
            below = panes[role] = self.pane_id(
                self.herdr("pane", "split", below, "--direction", "down", "--no-focus"), "pane")
        board_pane = self.pane_id(self.herdr("pane", "split", below, "--direction", "down", "--no-focus"), "pane")

        for role, pid in panes.items():               # best effort: friendly pane titles
            self.herdr("pane", "rename", pid, role, check=False)
        self.herdr("pane", "rename", board_pane, "board", check=False)

        self.herdr("pane", "run", board_pane, self.board_command())
        for role in producers + reviewers + [coord]:  # coordinator last so it boots with workers ready
            self.herdr("pane", "run", panes[role], self.agent_command(role))
        # Every split above uses --no-focus, so the workspace root/coordinator remains focused.

        if auto_request:
            text = (REPO / "demo_request.md").read_text().strip()
            if not self.dry:
                print(f"waiting {request_delay:.0f}s for the coordinator to boot…")
                time.sleep(request_delay)
            self.herdr("pane", "send-text", panes[coord], text, check=False)
            self.herdr("pane", "send-keys", panes[coord], "Enter", check=False)
        return {**panes, "board": board_pane}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print herdr commands, run nothing")
    ap.add_argument("--auto-request", action="store_true", help="type demo_request.md into the coordinator pane")
    ap.add_argument("--delay", type=float, default=15, help="seconds to wait before auto-typing the request")
    args = ap.parse_args()
    panes = Launcher(dry_run=args.dry_run).launch(args.auto_request, args.delay)
    print("\nPanes:", ", ".join(f"{r}={p}" for r, p in panes.items()))
    print("\nWorkspace is up. Click the coordinator pane and paste your request"
          if not args.auto_request else "\nRequest sent to the coordinator.")
    print("(the demo request lives in demo_request.md). Watch the board pane for handoffs.")


if __name__ == "__main__":
    main()
