import fnmatch
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


def branch_exists_locally(repo_path: Path, branch: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=repo_path,
            capture_output=True,
        ).returncode
        == 0
    )


def detect_default_branch(repo_path: Path, remote: str) -> str | None:
    # Ask the remote directly — authoritative, not affected by stale local state.
    result = subprocess.run(
        ["git", "ls-remote", "--symref", remote, "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        heads_prefix = "ref: refs/heads/"
        heads_suffix = "\tHEAD"
        for line in result.stdout.splitlines():
            if line.startswith(heads_prefix) and line.endswith(heads_suffix):
                return line[len(heads_prefix) : -len(heads_suffix)]

    # Fall back to the locally cached symref (set during clone/fetch).
    result = subprocess.run(
        ["git", "symbolic-ref", f"refs/remotes/{remote}/HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        ref = result.stdout.strip()
        prefix = f"refs/remotes/{remote}/"
        if ref.startswith(prefix):
            return ref[len(prefix) :]

    for candidate in ("main", "master", "develop"):
        if branch_exists_locally(repo_path, candidate):
            return candidate
    return None


def create_worktree(
    repo_path: Path,
    worktree_path: Path,
    branch: str,
    remote: str | None = None,
    base: str | None = None,
) -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    local_exists = branch_exists_locally(repo_path, branch)

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
        if base:
            cmd.append(base)

    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "already used by worktree" in stderr:
            match = re.search(r"already used by worktree at '([^']+)'", stderr)
            location = f" at {match.group(1)}" if match else ""
            raise WorktreeError(
                f"Branch '{branch}' is already checked out{location}. "
                f"Run 'orbit launch <new-branch>' to start on a different branch."
            )
        raise WorktreeError(f"Failed to create worktree: {stderr}")


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


def sync_untracked_to_worktree(
    source_path: Path,
    worktree_path: Path,
    patterns: list[str],
) -> list[str]:
    """Sync untracked files matching patterns from source into worktree.

    Uses git to enumerate all untracked files (including ignored ones like
    .env), then symlinks any whose basename matches one of the given fnmatch
    patterns.  Matching on the basename means '.*' catches dotfiles at any
    depth.

    For each file, ancestors are checked first so that a pattern like
    'node_modules' symlinks the whole directory rather than individual files.
    """
    result = subprocess.run(
        ["git", "ls-files", "--others"],
        cwd=source_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise WorktreeError(
            f"Failed to list untracked files in {source_path}: {result.stderr.strip()}"
        )

    already_synced: set[Path] = set()
    synced: list[str] = []

    for entry in result.stdout.splitlines():
        file_rel = Path(entry)

        # Check ancestors first (shallowest match wins), then the file itself.
        matched: Path | None = None
        parts = file_rel.parts
        candidates = [Path(*parts[: i + 1]) for i in range(len(parts))]
        for candidate in candidates:
            if any(fnmatch.fnmatch(candidate.name, pattern) for pattern in patterns):
                matched = candidate
                break

        if matched is None or matched in already_synced:
            continue

        already_synced.add(matched)
        src = source_path / matched
        dst = worktree_path / matched
        if dst.exists() or dst.is_symlink():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.symlink_to(src.resolve())
        synced.append(str(matched))

    return synced
