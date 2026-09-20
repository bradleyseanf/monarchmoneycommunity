"""Keep temporary Git repositories independent of the invoking hook's repo."""

import os
import subprocess
from unittest.mock import patch


def isolate_git_environment(test_case):
    clean_environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    local_variables = subprocess.check_output(
        ["git", "rev-parse", "--local-env-vars"],
        text=True,
        env=clean_environment,
    ).splitlines()
    for key in local_variables:
        clean_environment.pop(key, None)
    clean_environment.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
    )
    environment = patch.dict(os.environ, clean_environment, clear=True)
    environment.start()
    test_case.addCleanup(environment.stop)
