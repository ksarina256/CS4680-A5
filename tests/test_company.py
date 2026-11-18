"""Run with:  python3 -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from opc import engine as E, lint  # noqa: E402
import launch  # noqa: E402
import simulate  # noqa: E402
from compare import compare as comparison  # noqa: E402

BODY = """## Context
A realistic brief with enough text to pass the quality gate for task bodies in this engine.

## Acceptance criteria
- First measurable criterion
- Second measurable criterion
- Third measurable criterion
"""
NOTES = "1) Fix the opening. 2) Add sources. 3) Align naming with the research."


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["COMPANY_HOME"] = self.tmp.name
        E.init(reset=True)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COMPANY_HOME", None)

    def produce(self, role, text="x" * 400):
        a = E.wait(role, timeout=1, poll=0.05)
        self.assertIsNotNone(a, f"{role} should have work")
        a.task.output_path().write_text(text)
        E.submit(a.task.id, role)
        return a


class TaskCreation(Base):
    def test_rejects_thin_or_criteria_free_briefs(self):
        with self.assertRaises(E.OPCError):
            E.new_task("researcher", "t", "too short")
        with self.assertRaises(E.OPCError):
            E.new_task("researcher", "t", "word " * 80)  # long but no acceptance criteria

    def test_rejects_unknown_role_dependency_and_bad_output(self):
        with self.assertRaises(E.OPCError):
            E.new_task("intern", "t", BODY)
        with self.assertRaises(E.OPCError):
            E.new_task("researcher", "t", BODY, deps=["T99"])
        with self.assertRaises(E.OPCError):
            E.new_task("researcher", "t", BODY, output="../evil.md")
        with self.assertRaises(E.OPCError):
            E.new_task("coordinator", "t", BODY)

    def test_ids_increment_and_files_exist(self):
        a = E.new_task("researcher", "a", BODY)
        b = E.new_task("copywriter", "b", BODY, deps=["T01"])
        self.assertEqual((a.id, b.id), ("T01", "T02"))
        self.assertTrue(a.path.exists() and b.path.exists())
        self.assertEqual(b.deps, ["T01"])


class Workflow(Base):
    def test_dependency_gating(self):
        E.new_task("researcher", "r", BODY)
        E.new_task("copywriter", "c", BODY, deps=["T01"])
        self.assertIsNone(E.wait("copywriter", timeout=0.2, poll=0.05))   # blocked by T01
        self.produce("researcher")
        self.assertIsNone(E.wait("copywriter", timeout=0.2, poll=0.05))   # still not approved
        E.wait("reviewer", timeout=1, poll=0.05)
        E.review("T01", "revise", NOTES, "reviewer", 6)
        self.produce("researcher")
        E.wait("reviewer", timeout=1, poll=0.05)
        E.review("T01", "approve", NOTES, "reviewer", 9)
        self.assertEqual(E.wait("copywriter", timeout=1, poll=0.05).kind, "WORK")

    def test_first_draft_cannot_be_approved(self):
        E.new_task("researcher", "r", BODY)
        self.produce("researcher")
        with self.assertRaisesRegex(E.OPCError, "POLICY"):
            E.review("T01", "approve", NOTES, "reviewer", 9)

    def test_revision_loop_and_max_revisions(self):
        E.new_task("researcher", "r", BODY)
        self.produce("researcher")
        E.wait("reviewer", timeout=1, poll=0.05)
        E.review("T01", "revise", NOTES, "reviewer", 5)
        self.assertEqual(E.get_task("T01").status, E.CHANGES)
        a = E.wait("researcher", timeout=1, poll=0.05)
        self.assertEqual(a.kind, "REWORK")
        self.assertIn("REVIEWER FEEDBACK", E.format_assignment(a, "researcher"))
        a.task.output_path().write_text("y" * 400)
        E.submit("T01", "researcher")
        E.wait("reviewer", timeout=1, poll=0.05)
        E.review("T01", "revise", NOTES, "reviewer", 7)       # revision 2 == max
        self.produce("researcher")
        with self.assertRaisesRegex(E.OPCError, "max_revisions"):
            E.review("T01", "revise", NOTES, "reviewer", 7)
        E.review("T01", "approve", NOTES, "reviewer", 8)
        self.assertEqual(E.get_task("T01").status, E.DONE)
        self.assertEqual(E.get_task("T01").meta["scores"], "5,7,8")

    def test_guards(self):
        E.new_task("researcher", "r", BODY)
        with self.assertRaises(E.OPCError):                    # not claimed yet
            E.submit("T01", "researcher")
        a = E.wait("researcher", timeout=1, poll=0.05)
        with self.assertRaises(E.OPCError):                    # no deliverable on disk
            E.submit("T01", "researcher")
        with self.assertRaises(E.OPCError):                    # wrong role
            E.submit("T01", "copywriter")
        a.task.output_path().write_text("x" * 400)
        E.submit("T01", "researcher")
        with self.assertRaises(E.OPCError):                    # producers can't review
            E.review("T01", "revise", NOTES, "researcher")
        with self.assertRaises(E.OPCError):                    # vague notes
            E.review("T01", "revise", "meh", "reviewer")

    def test_review_score_is_bounded(self):
        E.new_task("researcher", "r", BODY)
        self.produce("researcher")
        E.wait("reviewer", timeout=1, poll=0.05)
        with self.assertRaisesRegex(E.OPCError, "0 to 10"):
            E.review("T01", "revise", NOTES, "reviewer", 11)
        with self.assertRaisesRegex(E.OPCError, "reviewer role is required"):
            E.review("T01", "revise", NOTES)

    def test_package_requires_all_done(self):
        E.new_task("researcher", "r", BODY)
        with self.assertRaises(E.OPCError):
            E.package()


class EndToEnd(unittest.TestCase):
    def test_simulation_completes_with_mixed_tools_and_revisions(self):
        with tempfile.TemporaryDirectory() as d:
            stats = simulate.run(Path(d), speed=0.01, quiet=True)
            self.assertEqual(stats["tasks_done"], stats["tasks"])
            self.assertGreaterEqual(stats["total_revisions"], 1)
            self.assertGreaterEqual(len(stats["tools_used"]), 2)
            self.assertGreaterEqual(len(stats["roles_used"]), 4)
            final = Path(d) / "final"
            for f in ("MANIFEST.md", "stats.json", "T03_developer.html", "T02_copywriter.md"):
                self.assertTrue((final / f).exists(), f)
            self.assertTrue(list((final / "reviews").glob("*round1.md")))
            res = lint.lint_html(final / "T03_developer.html", final / "T02_copywriter.md")
            self.assertTrue(all(ok for _, ok, _ in res), res)


class Lint(unittest.TestCase):
    def test_bad_page_fails_key_checks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.html"
            p.write_text("<html><body><h1>a</h1><h1>b</h1><img src='http://x/y.png'></body></html>")
            failed = {n for n, ok, _ in lint.lint_html(p) if not ok}
            for n in ("doctype present", "<html lang=...>", "exactly one <h1>", "all <img> have alt",
                      "self-contained (no external assets)", "responsive viewport meta"):
                self.assertIn(n, failed)


class Comparison(unittest.TestCase):
    def test_counts_rows_after_a_markdown_heading(self):
        text = """## 3. Competitor landscape

| Competitor | Price | Gap |
|---|---|---|
| A | free | x |
| B | $1 | y |

## Next section
"""
        self.assertEqual(comparison.count_table_rows_after(text, r"competitor"), 2)


class Launch(unittest.TestCase):
    def test_dry_run_builds_one_workspace_with_pane_per_agent(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            L = launch.Launcher(dry_run=True)
            panes = L.launch()
        team = E.load_team()
        roles = team["roles"]
        self.assertGreaterEqual(len(roles) - 1, 4)                      # >= 4 specialist roles + coordinator
        self.assertEqual(sum(c[1:3] == ["workspace", "create"] for c in L.calls), 1)   # ONE workspace
        runs = [c for c in L.calls if c[1:3] == ["pane", "run"]]
        self.assertEqual(len(runs), len(roles) + 1)                     # every agent + the board
        cmds = " ".join(c[4] for c in runs)
        self.assertIn("claude", cmds)
        self.assertIn("codex", cmds)                                    # >= 2 different AI tools
        for role in roles:
            self.assertIn(f"COMPANY_ROLE={role}", cmds)
            self.assertTrue((Path(__file__).resolve().parents[1] / roles[role]["instructions"]).exists())


if __name__ == "__main__":
    unittest.main()
