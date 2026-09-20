import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.git_test_support import isolate_git_environment

if os.name == "posix":
    import fcntl
    import pty
    import termios


HOOK = Path(__file__).resolve().parents[1] / ".githooks/pre-push"


@unittest.skipUnless(os.name == "posix", "The hook requires a POSIX terminal")
class TestPrePush(unittest.TestCase):
    def setUp(self):
        isolate_git_environment(self)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-q", "--template=")
        self.git("config", "core.hooksPath", ".git/hooks")
        self.git("config", "user.name", "Hook Test")
        self.git("config", "user.email", "hook@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.tracked = self.root / "code.py"
        self.tracked.write_text("original\n")
        (self.root / ".gitignore").write_text(".mm/\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        self.head = self.git("rev-parse", "HEAD")
        self.python = self.root / ".git/test-python"
        self.python.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "-c" ]; then exit 0; fi\n'
            "touch .git/test-ran\n"
            'case "${TEST_CHANGE:-}" in\n'
            "  file) echo changed >> code.py ;;\n"
            "  head) git commit --allow-empty -qm changed ;;\n"
            "esac\n"
            'exit "${TEST_EXIT:-0}"\n'
        )
        self.python.chmod(0o755)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def update(self, oid=None, ref="refs/heads/main"):
        return f"{ref} {oid or self.head} {ref} {'0' * 40}\n"

    def run_hook(self, updates=None, **environment):
        # Give the hook a controlling terminal while keeping Git's ref input on
        # stdin. The fake interpreter runs no imports, API calls, or prompts.
        master, slave = pty.openpty()
        try:
            return subprocess.run(
                ["sh", str(HOOK), "origin", "unused-remote"],
                cwd=self.root,
                input=self.update() if updates is None else updates,
                text=True,
                capture_output=True,
                env={**os.environ, "PYTHON": str(self.python), **environment},
                start_new_session=True,
                pass_fds=(slave,),
                preexec_fn=lambda: fcntl.ioctl(slave, termios.TIOCSCTTY, 0),
                timeout=10,
            )
        finally:
            os.close(master)
            os.close(slave)

    def assert_not_run(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / ".git/test-ran").exists())

    def test_clean_head_runs_live_checks(self):
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / ".git/test-ran").exists())

    def test_dirty_tracked_staged_and_untracked_changes_block_tests(self):
        for change in ("tracked", "staged", "untracked"):
            with self.subTest(change=change):
                self.git("reset", "--hard", "-q", self.head)
                if change == "untracked":
                    (self.root / "new_method.py").write_text("untracked\n")
                else:
                    self.tracked.write_text("changed\n")
                    if change == "staged":
                        self.git("add", "code.py")
                result = self.run_hook()
                self.assert_not_run(result)
                self.assertIn(
                    "must match the pushed commit and be clean", result.stderr
                )

    def test_ignored_session_files_do_not_block(self):
        (self.root / ".mm").mkdir()
        (self.root / ".mm/session").write_text("unused test session")
        self.assertEqual(self.run_hook().returncode, 0)

    def test_non_checked_out_commit_in_multiple_ref_push_blocks(self):
        self.git("commit", "--allow-empty", "-qm", "second")
        current = self.git("rev-parse", "HEAD")
        result = self.run_hook(
            self.update(current) + self.update(ref="refs/heads/other")
        )
        self.assert_not_run(result)
        self.assertIn("does not point to the checked-out commit", result.stderr)

    def test_annotated_tag_pointing_to_head_is_allowed(self):
        self.git("-c", "tag.gpgsign=false", "tag", "-am", "release", "test-release")
        tag = self.git("rev-parse", "test-release")
        result = self.run_hook(self.update(tag, "refs/tags/test-release"))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_deletion_only_or_empty_push_needs_no_clean_checkout_or_tests(self):
        self.tracked.write_text("dirty\n")
        for updates in ("", f"(delete) {'0' * 40} refs/heads/old {self.head}\n"):
            with self.subTest(updates=updates):
                result = self.run_hook(updates)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.root / ".git/test-ran").exists())

    def test_live_check_failure_blocks_push(self):
        result = self.run_hook(TEST_EXIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run_tests.py failed", result.stderr)

    def test_changes_during_live_tests_block_push(self):
        for change in ("file", "head"):
            with self.subTest(change=change):
                self.git("reset", "--hard", "-q", self.head)
                result = self.run_hook(TEST_CHANGE=change)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "must match the pushed commit and be clean", result.stderr
                )
