import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.git_test_support import isolate_git_environment


class TestGitEnvironmentIsolation(unittest.TestCase):
    def test_hook_exported_git_environment_cannot_change_invoking_repository(self):
        isolate_git_environment(self)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def git(*arguments):
                return subprocess.check_output(
                    ["git", *arguments], cwd=root, text=True
                ).strip()

            git("init", "-q", "--template=")
            git("config", "user.name", "Isolation Test")
            git("config", "user.email", "isolation@example.invalid")
            tracked = root / "preserve-me"
            tracked.write_text("committed\n")
            git("add", ".")
            git("commit", "-qm", "initial")
            head = git("rev-parse", "HEAD")
            tracked.write_text("uncommitted work\n")
            untracked = root / "untracked-work"
            untracked.write_text("keep this too\n")
            before = {
                path: (root / path).read_bytes()
                for path in (
                    ".git/HEAD",
                    ".git/config",
                    ".git/index",
                    "preserve-me",
                    "untracked-work",
                )
            }
            environment = {
                **os.environ,
                "GIT_DIR": str(root / ".git"),
                "GIT_COMMON_DIR": str(root / ".git"),
                "GIT_WORK_TREE": str(root),
                "GIT_INDEX_FILE": str(root / ".git/index"),
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.hooksPath",
                "GIT_CONFIG_VALUE_0": str(root / "shared-hooks"),
                "GIT_TEMPLATE_DIR": str(root / "must-not-use-template"),
            }
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "tests.test_install_hooks",
                    "tests.test_pre_push",
                    "-q",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                text=True,
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for path, contents in before.items():
                self.assertEqual((root / path).read_bytes(), contents, path)
            self.assertEqual(git("rev-parse", "HEAD"), head)
            self.assertFalse((root / "shared-hooks").exists())
