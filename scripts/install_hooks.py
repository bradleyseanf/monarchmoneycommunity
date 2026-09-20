#!/usr/bin/env python3
"""Install only the project's pre-push hook, preserving other Git hooks."""

import subprocess
from pathlib import Path

WRAPPER = """#!/bin/sh
# monarchmoneycommunity pre-push hook
set -eu
repo_root="$(git rev-parse --show-toplevel)"
exec "$repo_root/.githooks/pre-push" "$@"
"""


def install_hook(root: Path) -> None:
    hook_path = subprocess.check_output(
        ["git", "rev-parse", "--git-path", "hooks/pre-push"],
        cwd=root,
        text=True,
    ).strip()
    hook = root / hook_path
    source = root / ".githooks" / "pre-push"
    if hook.resolve() == source.resolve():
        print("The versioned pre-push hook is already active.")
        return
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.exists() or hook.is_symlink():
        if not hook.is_symlink() and hook.read_text() == WRAPPER:
            hook.chmod(hook.stat().st_mode | 0o111)
            print("The pre-push hook is already installed.")
            return
        raise SystemExit(
            f"Existing hook preserved: {hook}. Integrate .githooks/pre-push "
            "with your existing pre-push hook manually; both hooks must receive "
            "the original arguments and stdin, and either failure must block the push."
        )
    # Exclusive creation ensures an existing hook is never overwritten.
    with hook.open("x") as stream:
        stream.write(WRAPPER)
    hook.chmod(hook.stat().st_mode | 0o111)
    print(f"Installed {hook}; other hooks and core.hooksPath are unchanged.")


if __name__ == "__main__":
    install_hook(Path(__file__).resolve().parents[1])
