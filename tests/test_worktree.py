import subprocess

import pytest

from orbit.worktree import (
    WorktreeError,
    choose_remote,
    create_worktree,
    detect_branch,
    detect_default_branch,
    get_main_repo_path,
    get_remotes,
    has_uncommitted_changes,
    remove_worktree,
    slugify,
    sync_local_branch_with_remote,
    sync_untracked_to_worktree,
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


@pytest.mark.integration
class TestSyncUntrackedToWorktree:
    def test_symlinks_dotfile(self, git_repo, tmp_path):
        (git_repo / ".env").write_text("SECRET=123\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".env"])
        assert synced == [".env"]
        dst = worktree_path / ".env"
        assert dst.is_symlink()
        assert dst.resolve() == (git_repo / ".env").resolve()

    def test_symlink_reflects_source_changes(self, git_repo, tmp_path):
        env_file = git_repo / ".env"
        env_file.write_text("SECRET=original\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        sync_untracked_to_worktree(git_repo, worktree_path, [".env"])
        env_file.write_text("SECRET=updated\n")
        assert (worktree_path / ".env").read_text() == "SECRET=updated\n"

    def test_symlinks_non_dotfile_directory(self, git_repo, tmp_path):
        node_modules = git_repo / "node_modules"
        node_modules.mkdir()
        (node_modules / "pkg.js").write_text("module.exports = {}\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, ["node_modules"])
        assert synced == ["node_modules"]
        dst = worktree_path / "node_modules"
        assert dst.is_symlink()
        assert dst.resolve() == (git_repo / "node_modules").resolve()

    def test_symlinks_non_dotfile_regular_file(self, git_repo, tmp_path):
        (git_repo / "build.log").write_text("ok\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, ["build.log"])
        assert synced == ["build.log"]
        dst = worktree_path / "build.log"
        assert dst.is_symlink()
        assert dst.resolve() == (git_repo / "build.log").resolve()

    def test_skips_git_tracked_files(self, git_repo, tmp_path):
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, ["README.md"])
        assert synced == []

    def test_skips_already_existing_destination(self, git_repo, tmp_path):
        (git_repo / ".env").write_text("A=1\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        (worktree_path / ".env").write_text("already here\n")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".env"])
        assert synced == []

    def test_no_match_returns_empty(self, git_repo, tmp_path):
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".env"])
        assert synced == []

    def test_skips_git_directory(self, git_repo, tmp_path):
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, ["*", ".*"])
        assert ".git" not in synced
        assert not (worktree_path / ".git").is_symlink()

    def test_glob_pattern_matches_multiple(self, git_repo, tmp_path):
        (git_repo / ".env").write_text("A=1\n")
        (git_repo / ".env.local").write_text("B=2\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".env*"])
        assert sorted(synced) == [".env", ".env.local"]
        assert (worktree_path / ".env").is_symlink()
        assert (worktree_path / ".env.local").is_symlink()

    def test_syncs_gitignored_dotfile(self, git_repo, tmp_path):
        (git_repo / ".gitignore").write_text(".env\n")
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add gitignore"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        (git_repo / ".env").write_text("SECRET=123\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".env"])
        assert synced == [".env"]
        dst = worktree_path / ".env"
        assert dst.is_symlink()
        assert dst.resolve() == (git_repo / ".env").resolve()

    def test_ignores_node_modules_with_dotfile_pattern(self, git_repo, tmp_path):
        (git_repo / ".gitignore").write_text("node_modules/\n.env\n")
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add gitignore"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        node_modules = git_repo / "node_modules"
        node_modules.mkdir()
        (node_modules / "pkg.js").write_text("module.exports = {}\n")
        (git_repo / ".env").write_text("SECRET=123\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".*"])
        assert ".env" in synced
        assert "node_modules" not in synced
        assert not (worktree_path / "node_modules").exists()

    def test_name_pattern_does_not_match_nested_dotfile(self, git_repo, tmp_path):
        (git_repo / ".env").write_text("ROOT=1\n")
        pkg_dir = git_repo / "packages" / "api"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / ".env").write_text("DB=postgres\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".*"])
        assert ".env" in synced
        assert "packages/api/.env" not in synced
        assert not (worktree_path / "packages").exists()

    def test_path_pattern_matches_nested_dotfile(self, git_repo, tmp_path):
        pkg_dir = git_repo / "packages" / "api"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / ".env").write_text("DB=postgres\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(
            git_repo, worktree_path, ["packages/api/.env"]
        )
        assert "packages/api/.env" in synced
        dst = worktree_path / "packages" / "api" / ".env"
        assert dst.is_symlink()
        assert dst.resolve() == (pkg_dir / ".env").resolve()

    def test_name_pattern_does_not_sync_node_modules_dotfile(self, git_repo, tmp_path):
        (git_repo / ".gitignore").write_text("node_modules/\n")
        node_modules = git_repo / "node_modules"
        node_modules.mkdir()
        (node_modules / ".cache").mkdir()
        (node_modules / ".cache" / "data.json").write_text("{}\n")
        (git_repo / ".env").write_text("SECRET=123\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".*"])
        assert ".env" in synced
        assert not (worktree_path / "node_modules").exists()

    def test_wildcard_does_not_sync_dot_directory(self, git_repo, tmp_path):
        """Wildcard patterns like .* must not auto-symlink dot-directories."""
        dot_store = git_repo / ".pnpm-store"
        dot_store.mkdir()
        (dot_store / "some-hash").mkdir()
        (dot_store / "some-hash" / "pkg.js").write_text("module.exports = {}\n")
        (git_repo / ".env").write_text("SECRET=123\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".*"])
        assert ".env" in synced
        assert ".pnpm-store" not in synced
        assert not (worktree_path / ".pnpm-store").exists()

    def test_exact_dot_directory_pattern_still_symlinks(self, git_repo, tmp_path):
        """Exact name patterns (no wildcards) may still symlink dot-directories."""
        dot_cache = git_repo / ".cache"
        dot_cache.mkdir()
        (dot_cache / "data.bin").write_text("cached\n")
        worktree_path = tmp_path / "wt"
        create_worktree(git_repo, worktree_path, "feat")
        synced = sync_untracked_to_worktree(git_repo, worktree_path, [".cache"])
        assert ".cache" in synced
        assert (worktree_path / ".cache").is_symlink()


@pytest.mark.integration
class TestSyncLocalBranchWithRemote:
    def _make_commit(self, repo, message):
        (repo / "file.txt").write_text(f"{message}\n")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo,
            check=True,
            capture_output=True,
        )

    def _setup_remote(self, git_repo, tmp_path):
        bare = tmp_path / "bare"
        subprocess.run(
            ["git", "clone", "--bare", str(git_repo), str(bare)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", str(bare)],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        return bare

    def test_returns_none_when_no_remote_branch(self, git_repo, tmp_path):
        self._setup_remote(git_repo, tmp_path)
        subprocess.run(
            ["git", "branch", "feat"], cwd=git_repo, check=True, capture_output=True
        )
        notice = sync_local_branch_with_remote(git_repo, "feat", "origin")
        assert notice is None

    def test_fast_forwards_when_behind(self, git_repo, tmp_path):
        bare = self._setup_remote(git_repo, tmp_path)
        subprocess.run(
            ["git", "branch", "feat"], cwd=git_repo, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push", "origin", "feat"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        # Advance remote feat via a temp clone.
        tmp_clone = tmp_path / "tmp_clone"
        subprocess.run(
            ["git", "clone", str(bare), str(tmp_clone)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "feat"],
            cwd=tmp_clone,
            check=True,
            capture_output=True,
        )
        self._make_commit(tmp_clone, "remote-commit")
        subprocess.run(
            ["git", "push", "origin", "feat"],
            cwd=tmp_clone,
            check=True,
            capture_output=True,
        )

        notice = sync_local_branch_with_remote(git_repo, "feat", "origin")

        assert notice is not None
        assert "Fast-forwarded" in notice
        local_sha = subprocess.run(
            ["git", "rev-parse", "feat"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        ).stdout.strip()
        remote_sha = subprocess.run(
            ["git", "rev-parse", "origin/feat"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert local_sha == remote_sha

    def test_returns_none_when_ahead(self, git_repo, tmp_path):
        self._setup_remote(git_repo, tmp_path)
        subprocess.run(
            ["git", "branch", "feat"], cwd=git_repo, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push", "origin", "feat"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        # Add a local-only commit to feat.
        subprocess.run(
            ["git", "checkout", "feat"], cwd=git_repo, check=True, capture_output=True
        )
        self._make_commit(git_repo, "local-only-commit")
        subprocess.run(
            ["git", "checkout", "-"], cwd=git_repo, check=True, capture_output=True
        )

        notice = sync_local_branch_with_remote(git_repo, "feat", "origin")

        assert notice is None

    def test_returns_warning_when_diverged(self, git_repo, tmp_path):
        bare = self._setup_remote(git_repo, tmp_path)
        subprocess.run(
            ["git", "branch", "feat"], cwd=git_repo, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push", "origin", "feat"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        # Add a local commit to feat.
        subprocess.run(
            ["git", "checkout", "feat"], cwd=git_repo, check=True, capture_output=True
        )
        self._make_commit(git_repo, "local-commit")
        subprocess.run(
            ["git", "checkout", "-"], cwd=git_repo, check=True, capture_output=True
        )
        # Also advance remote feat via a temp clone (original tip, so it diverges).
        tmp_clone = tmp_path / "tmp_clone"
        subprocess.run(
            ["git", "clone", str(bare), str(tmp_clone)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "feat"],
            cwd=tmp_clone,
            check=True,
            capture_output=True,
        )
        self._make_commit(tmp_clone, "remote-commit")
        subprocess.run(
            ["git", "push", "origin", "feat"],
            cwd=tmp_clone,
            check=True,
            capture_output=True,
        )

        notice = sync_local_branch_with_remote(git_repo, "feat", "origin")

        assert notice is not None
        assert "diverged" in notice


class TestDetectDefaultBranch:
    def test_detect_default_branch_via_symbolic_ref(self, git_repo):
        subprocess.run(
            [
                "git",
                "symbolic-ref",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/main",
            ],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        result = detect_default_branch(git_repo, "origin")
        assert result == "main"

    def test_detect_default_branch_fallback_to_main(self, git_repo):
        result = detect_default_branch(git_repo, "origin")
        assert result in ("main", "master")

    def test_detect_default_branch_returns_none(self, git_repo):
        current = detect_branch(git_repo)
        subprocess.run(
            ["git", "branch", "-m", current, "custom-branch"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        result = detect_default_branch(git_repo, "origin")
        assert result is None

    def test_detect_default_branch_queries_remote_when_no_symref(
        self, git_repo, tmp_path
    ):
        subprocess.run(
            ["git", "checkout", "-b", "dev"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        bare = tmp_path / "bare"
        subprocess.run(
            ["git", "clone", "--bare", str(git_repo), str(bare)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", str(bare)],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        result = detect_default_branch(git_repo, "origin")
        assert result == "dev"

    def test_detect_default_branch_prefers_remote_over_stale_symref(
        self, git_repo, tmp_path
    ):
        # Remote's default is 'dev', but local symref still points to 'main'.
        subprocess.run(
            ["git", "checkout", "-b", "dev"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        bare = tmp_path / "bare"
        subprocess.run(
            ["git", "clone", "--bare", str(git_repo), str(bare)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "origin", str(bare)],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        # Simulate stale local symref pointing to the old default.
        subprocess.run(
            [
                "git",
                "symbolic-ref",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/main",
            ],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        result = detect_default_branch(git_repo, "origin")
        assert result == "dev"
