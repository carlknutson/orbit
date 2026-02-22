import subprocess

import pytest

from orbit.tmux import TmuxError


@pytest.fixture(autouse=True)
def _prevent_execvp(monkeypatch):
    """Prevent os.execvp from replacing the test process.

    attach_session and attach_and_choose use os.execvp, which would replace the
    pytest process with tmux and prevent cleanup from running.  Raising TmuxError
    lets the existing ``except TmuxError`` blocks in tests handle it normally.
    """

    def _no_exec(*_args, **_kwargs):
        raise TmuxError("execvp blocked in tests")

    monkeypatch.setattr("orbit.tmux.os.execvp", _no_exec)


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo with one commit, suitable for worktree tests."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# Test\n")
    (repo / ".gitignore").write_text(".orbit/\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo
