import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.install_hooks import WRAPPER, install_hook
from tests.git_test_support import isolate_git_environment


class TestInstallHooks(unittest.TestCase):
    def setUp(self):
        isolate_git_environment(self)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-q", "--template=")
        (self.root / ".git/hooks").mkdir()
        (self.root / ".git/info").mkdir()
        # Isolate these test repositories from any globally configured hook path.
        self.git("config", "core.hooksPath", ".git/hooks")
        redirect = contextlib.redirect_stdout(io.StringIO())
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def test_install_is_idempotent_and_preserves_other_hooks(self):
        hooks = self.root / ".git/hooks"
        other = hooks / "pre-commit"
        other.write_text("existing pre-commit")
        install_hook(self.root)
        install_hook(self.root)
        self.assertEqual((hooks / "pre-push").read_text(), WRAPPER)
        self.assertTrue((hooks / "pre-push").stat().st_mode & 0o111)
        self.assertEqual(other.read_text(), "existing pre-commit")
        self.assertEqual(self.git("config", "core.hooksPath"), ".git/hooks")

    def test_existing_pre_push_is_never_overwritten(self):
        hook = self.root / ".git/hooks/pre-push"
        hook.write_text("existing pre-push")
        with self.assertRaisesRegex(SystemExit, "Existing hook preserved"):
            install_hook(self.root)
        self.assertEqual(hook.read_text(), "existing pre-push")

    def test_configured_hook_directory_is_respected(self):
        self.git("config", "core.hooksPath", "custom hooks")
        (self.root / ".git/info/exclude").write_text("/custom hooks/pre-push\n")
        install_hook(self.root)
        self.assertEqual((self.root / "custom hooks/pre-push").read_text(), WRAPPER)
        self.assertEqual(self.git("config", "core.hooksPath"), "custom hooks")

    def test_unignored_custom_hook_is_not_created(self):
        self.git("config", "core.hooksPath", "custom hooks")
        with self.assertRaisesRegex(SystemExit, "must be ignored"):
            install_hook(self.root)
        self.assertFalse((self.root / "custom hooks").exists())

    def test_global_shared_hook_directory_is_untouched(self):
        with tempfile.TemporaryDirectory() as shared:
            shared_root = Path(shared)
            hooks = shared_root / "hooks"
            hooks.mkdir()
            existing = hooks / "pre-commit"
            existing.write_text("existing global hook")
            global_config = shared_root / "gitconfig"
            self.git(
                "config", "--file", str(global_config), "core.hooksPath", str(hooks)
            )
            self.git("config", "--unset", "core.hooksPath")
            with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(global_config)}):
                with self.assertRaisesRegex(SystemExit, "Shared or external"):
                    install_hook(self.root)
                self.assertEqual(self.git("config", "core.hooksPath"), str(hooks))
            self.assertEqual(existing.read_text(), "existing global hook")
            self.assertFalse((hooks / "pre-push").exists())

    def test_symlink_to_external_hook_directory_is_untouched(self):
        with tempfile.TemporaryDirectory() as shared:
            (self.root / "custom hooks").symlink_to(shared, target_is_directory=True)
            self.git("config", "core.hooksPath", "custom hooks")
            with self.assertRaisesRegex(SystemExit, "Shared or external"):
                install_hook(self.root)
            self.assertFalse((Path(shared) / "pre-push").exists())

    def test_wrapper_forwards_arguments_stdin_and_failure(self):
        source = self.root / ".githooks/pre-push"
        source.parent.mkdir()
        source.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\ncat\nexit 7\n')
        source.chmod(0o755)
        install_hook(self.root)
        result = subprocess.run(
            [str(self.root / ".git/hooks/pre-push"), "origin", "remote path"],
            cwd=self.root,
            input="refs/heads/main abc refs/heads/main def\n",
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 7)
        self.assertEqual(
            result.stdout,
            "origin\nremote path\nrefs/heads/main abc refs/heads/main def\n",
        )
