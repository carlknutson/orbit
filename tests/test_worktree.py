import subprocess

import pytest

from orbit.worktree import (
    WorktreeError,
    choose_remote,
    create_worktree,
    detect_branch,
    ensure_gitignore_has_orbit,
    get_main_repo_path,
    get_remotes,
    has_uncommitted_changes,
    remove_worktree,
    slugify,
)


class TestSlugify:
    def test_simple_branch(self):
        assert slugify("main") == "main"

    def test_slash_becomes_hyphen(self):
        assert slugify("feature/auth-flow") == "feature-auth-flow"

    def test_slash_preserves_full_path(self):
        assert slugify("bugfix/auth-flow") == "bugfix-auth-flow"

    def test_uppercase_lowercased(self):
        assert slugify("fix/FOO_bar") == "fix-foo-bar"

    def test_underscores_become_hyphens(self):
        assert slugify("fix_foo") == "fix-foo"

    def test_consecutive_hyphens_collapsed(self):
        assert slugify("foo--bar") == "foo-bar"

    def test_leading_trailing_hyphens_stripped(self):
        assert slugify("-foo-") == "foo"

    def test_truncated_to_40_chars(self):
        long = "a" * 50
        assert len(slugify(long)) == 40

    def test_special_chars_become_hyphens(self):
        assert slugify("foo@bar") == "foo-bar"

    def test_slash_and_special(self):
        assert slugify("feature/FOO_bar") == "feature-foo-bar"


@pytest.mark.integration
class TestDetectBranch:
    def test_returns_current_branch(self, git_repo):
        branch = detect_branch(git_repo)
        # default branch name may vary (main or master)
        assert branch in ("main", "master")

    def test_returns_new_branch_after_checkout(self, git_repo):
        subprocess.run(
            ["git", "checkout", "-b", "my-feature"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        assert detect_branch(git_repo) == "my-feature"

    def test_raises_for_nonexistent_path(self, tmp_path):
        with pytest.raises(WorktreeError):
            detect_branch(tmp_path / "nonexistent")


@pytest.mark.integration
class TestGetRemotes:
    def test_empty_for_no_remotes(self, git_repo):
        assert get_remotes(git_repo) == []

    def test_returns_sorted_remotes(self, git_repo, tmp_path):
        remote_a = tmp_path / "remote_a"
        remote_a.mkdir()
        run = lambda cmd, **kw: subprocess.run(  # noqa: E731
            cmd, check=True, capture_output=True, **kw
        )
        run(["git", "clone", "--bare", str(git_repo), str(remote_a)])
        run(["git", "remote", "add", "bravo", str(remote_a)], cwd=git_repo)
        run(["git", "remote", "add", "alpha", str(remote_a)], cwd=git_repo)
        remotes = get_remotes(git_repo)
        assert remotes == ["alpha", "bravo"]


@pytest.mark.integration
class TestChooseRemote:
    def test_returns_none_for_no_remotes(self, git_repo):
        remote, notice = choose_remote(git_repo)
        assert remote is None
        assert notice is None

    def _add_bare_remote(self, git_repo, tmp_path, name):
        bare = tmp_path / "bare"
        bare.mkdir()
        subprocess.run(
            ["git", "clone", "--bare", str(git_repo), str(bare)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", name, str(bare)],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

    def test_returns_origin_when_present(self, git_repo, tmp_path):
        self._add_bare_remote(git_repo, tmp_path, "origin")
        remote, notice = choose_remote(git_repo)
        assert remote == "origin"
        assert notice is None

    def test_returns_first_alpha_with_notice_when_no_origin(self, git_repo, tmp_path):
        self._add_bare_remote(git_repo, tmp_path, "upstream")
        remote, notice = choose_remote(git_repo)
        assert remote == "upstream"
        assert notice is not None
        assert "upstream" in notice


@pytest.mark.integration
class TestCreateWorktree:
    def test_creates_new_local_branch(self, git_repo, tmp_path):
        worktree_path = tmp_path / "worktrees" / "myapp-feat"
        create_worktree(git_repo, worktree_path, "feat", remote=None)
        assert worktree_path.exists()
        assert (worktree_path / "README.md").exists()

    def test_creates_worktree_for_existing_local_branch(self, git_repo, tmp_path):
        subprocess.run(
            ["git", "branch", "existing"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "existing", remote=None)
        assert worktree_path.exists()

    def test_raises_on_invalid_repo(self, tmp_path):
        with pytest.raises(WorktreeError):
            create_worktree(tmp_path, tmp_path / "wt", "branch")


@pytest.mark.integration
class TestRemoveWorktree:
    def test_removes_worktree(self, git_repo, tmp_path):
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        assert worktree_path.exists()
        remove_worktree(git_repo, worktree_path)
        assert not worktree_path.exists()


@pytest.mark.integration
class TestGetMainRepoPath:
    def test_returns_main_repo_from_worktree(self, git_repo, tmp_path):
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        result = get_main_repo_path(worktree_path)
        assert result.resolve() == git_repo.resolve()

    def test_returns_self_from_main_repo(self, git_repo):
        result = get_main_repo_path(git_repo)
        assert result.resolve() == git_repo.resolve()


@pytest.mark.integration
class TestHasUncommittedChanges:
    def test_clean_repo_returns_false(self, git_repo):
        assert not has_uncommitted_changes(git_repo)

    def test_modified_file_returns_true(self, git_repo):
        (git_repo / "README.md").write_text("changed\n")
        assert has_uncommitted_changes(git_repo)

    def test_untracked_file_returns_true(self, git_repo):
        (git_repo / "new_file.txt").write_text("hello\n")
        assert has_uncommitted_changes(git_repo)

    def test_staged_file_returns_true(self, git_repo):
        (git_repo / "README.md").write_text("staged change\n")
        subprocess.run(
            ["git", "add", "."], cwd=git_repo, check=True, capture_output=True
        )
        assert has_uncommitted_changes(git_repo)


class TestEnsureGitignoreHasOrbit:
    def test_creates_gitignore_when_missing(self, tmp_path):
        ensure_gitignore_has_orbit(tmp_path)
        assert (tmp_path / ".gitignore").read_text() == ".orbit/\n"

    def test_appends_to_existing_gitignore(self, tmp_path):
        (tmp_path / ".gitignore").write_text("node_modules/\n")
        ensure_gitignore_has_orbit(tmp_path)
        content = (tmp_path / ".gitignore").read_text()
        assert ".orbit/" in content
        assert "node_modules/" in content

    def test_idempotent_when_entry_present(self, tmp_path):
        (tmp_path / ".gitignore").write_text(".orbit/\n")
        ensure_gitignore_has_orbit(tmp_path)
        assert (tmp_path / ".gitignore").read_text() == ".orbit/\n"

    def test_adds_newline_before_entry_if_missing(self, tmp_path):
        (tmp_path / ".gitignore").write_text("node_modules/")
        ensure_gitignore_has_orbit(tmp_path)
        content = (tmp_path / ".gitignore").read_text()
        assert "node_modules/\n.orbit/\n" == content
