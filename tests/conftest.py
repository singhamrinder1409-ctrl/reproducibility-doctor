import os
import subprocess

import pytest


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "project"
    root.mkdir()

    def git(*args, input=None):
        return (
            subprocess.run(
                ["git", "-C", str(root), *args],
                input=input,
                capture_output=True,
                check=True,
                env={
                    **os.environ,
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_AUTHOR_NAME": "Fixture",
                    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                    "GIT_COMMITTER_NAME": "Fixture",
                    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
                },
            )
            .stdout.decode()
            .strip()
        )

    git("init", "--template=", "--object-format=sha1")
    (root / "README.md").write_text("# Controlled fixture\n\n```sh\npython hello.py\n```\n")
    (root / "hello.py").write_text("raise SystemExit(0)\n")
    git("add", ".")
    git("commit", "-m", "fixture")
    return root, git
