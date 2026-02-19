import re
import subprocess
from pathlib import Path


class WorktreeError(Exception):
    pass


def slugify(branch: str) -> str:
    slug = branch.lower()
    slug = slug.replace("/", "-")
    slug = re.sub(r"[^a-z0-9-]", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug[:40]


def detect_branch(repo_path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
    except OSError as e:
        raise WorktreeError(f"Failed to detect branch: {e}") from e
    if result.returncode != 0:
        raise WorktreeError(f"Failed to detect branch: {result.stderr.strip()}")
    branch = result.stdout.strip()
    if branch == "HEAD":
        raise WorktreeError("Repository is in detached HEAD state")
    return branch


def get_remotes(repo_path: Path) -> list[str]:
    result = subprocess.run(
        ["git", "remote"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise WorktreeError(f"Failed to list remotes: {result.stderr.strip()}")
    return sorted(r for r in result.stdout.splitlines() if r)


def remote_branch_exists(repo_path: Path, remote: str, branch: str) -> bool:
    result = subprocess.run(
        ["git", "ls-remote", "--heads", remote, branch],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def choose_remote(repo_path: Path) -> tuple[str | None, str | None]:
    remotes = get_remotes(repo_path)
    if not remotes:
        return None, None
    if "origin" in remotes:
        return "origin", None
    remote = remotes[0]
    return remote, f"No 'origin' remote found; using '{remote}'"


def create_worktree(
    repo_path: Path,
    worktree_path: Path,
    branch: str,
    remote: str | None = None,
) -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    local_exists = (
        subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=repo_path,
            capture_output=True,
        ).returncode
        == 0
    )

    if local_exists:
        cmd = ["git", "worktree", "add", str(worktree_path), branch]
    elif remote and remote_branch_exists(repo_path, remote, branch):
        fetch = subprocess.run(
            ["git", "fetch", remote, branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if fetch.returncode != 0:
            raise WorktreeError(f"Failed to fetch branch: {fetch.stderr.strip()}")
        cmd = [
            "git",
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree_path),
            f"{remote}/{branch}",
        ]
    else:
        cmd = ["git", "worktree", "add", "-b", branch, str(worktree_path)]

    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    if result.returncode != 0:
        raise WorktreeError(f"Failed to create worktree: {result.stderr.strip()}")


def remove_worktree(repo_path: Path, worktree_path: Path) -> None:
    result = subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise WorktreeError(f"Failed to remove worktree: {result.stderr.strip()}")


def get_main_repo_path(worktree_path: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise WorktreeError("Failed to find main git repository")
    git_dir = Path(result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = worktree_path / git_dir
    return git_dir.parent


def has_uncommitted_changes(worktree_path: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def ensure_gitignore_has_orbit(worktree_path: Path) -> None:
    gitignore = worktree_path / ".gitignore"
    entry = ".orbit/"
    if gitignore.exists():
        content = gitignore.read_text()
        if entry in content.splitlines():
            return
        if not content.endswith("\n"):
            content += "\n"
        gitignore.write_text(content + entry + "\n")
    else:
        gitignore.write_text(entry + "\n")
