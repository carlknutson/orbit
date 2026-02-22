import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from orbit.config import Config
from orbit.models import Orbit, Planet
from orbit.session import destroy, launch
from orbit.state import State, load_state
from orbit.tmux import TmuxError, kill_session, session_exists


def make_planet(repo_path: Path, windows=None, sync_untracked=None) -> Planet:
    kwargs: dict = {"name": "My App", "path": str(repo_path), "windows": windows or []}
    if sync_untracked is not None:
        kwargs["sync_untracked"] = sync_untracked
    return Planet(**kwargs)


def make_config(planet: Planet) -> Config:
    return Config(planets=[planet])


@pytest.mark.integration
class TestStart:
    def test_creates_tmux_session(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        orbit_name = None
        try:
            runner = CliRunner()
            with runner.isolated_filesystem():
                launch(
                    branch="feat",
                    name="test-orbit",
                    config=config,
                    state=state,
                    cwd=git_repo,
                    state_path=state_file,
                )
            orbit_name = "test-orbit"
            assert session_exists("test-orbit")
        finally:
            if orbit_name and session_exists(orbit_name):
                kill_session(orbit_name)

    def test_records_orbit_in_state(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            launch(
                branch="feat",
                name="test-state",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            saved = load_state(state_file)
            assert "test-state" in saved.orbits
            orbit = saved.orbits["test-state"]
            assert orbit.branch == "feat"
            assert orbit.planet == git_repo.name
        finally:
            if session_exists("test-state"):
                kill_session("test-state")

    def test_creates_worktree_directory(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            launch(
                branch="feat",
                name="test-wt",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            assert (git_repo.parent / f"{git_repo.name}.wt" / "test-wt").exists()
        finally:
            if session_exists("test-wt"):
                kill_session("test-wt")

    def test_gitignore_has_orbit_entry(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            launch(
                branch="feat",
                name="test-gi",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            wt_dir = git_repo.parent / f"{git_repo.name}.wt" / "test-gi"
            gitignore = wt_dir / ".gitignore"
            assert ".orbit/" in gitignore.read_text().splitlines()
        finally:
            if session_exists("test-gi"):
                kill_session("test-gi")

    def test_collision_with_live_session_raises(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            launch(
                branch="feat",
                name="test-coll",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            state2 = load_state(state_file)
            with pytest.raises(Exception, match="already exists"):
                launch(
                    branch="feat2",
                    name="test-coll",
                    config=config,
                    state=state2,
                    cwd=git_repo,
                    state_path=state_file,
                )
        finally:
            if session_exists("test-coll"):
                kill_session("test-coll")

    def test_auto_numbered_on_default_name_collision(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        # Simulate a pre-existing "feat" orbit from another planet so the
        # default name collides and auto-numbering kicks in.
        state.add(
            Orbit(
                name="feat",
                planet="other-planet",
                branch="feat",
                worktree=str(tmp_path / "other" / "feat"),
                tmux_session="feat",
            )
        )

        try:
            launch(
                branch="feat",
                name=None,
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            saved = load_state(state_file)
            assert "feat-2" in saved.orbits
        finally:
            if session_exists("feat-2"):
                kill_session("feat-2")

    def test_sync_untracked_creates_symlink_for_dotfile(self, git_repo, tmp_path):
        (git_repo / ".env").write_text("SECRET=abc\n")
        planet = make_planet(git_repo, sync_untracked=[".env"])
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            launch(
                branch="feat",
                name="test-sync",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            dst = git_repo.parent / f"{git_repo.name}.wt" / "test-sync" / ".env"
            assert dst.is_symlink()
            assert dst.resolve() == (git_repo / ".env").resolve()
        finally:
            if session_exists("test-sync"):
                kill_session("test-sync")

    def test_stale_orbit_raises(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        stale_orbit = Orbit(
            name="stale-orbit",
            planet=git_repo.name,
            branch="main",
            worktree=str(git_repo.parent / f"{git_repo.name}.wt" / "stale-orbit"),
            tmux_session="stale-orbit",
        )
        state = State()
        state.add(stale_orbit)

        with pytest.raises(Exception, match="stale"):
            launch(
                branch="feat",
                name="stale-orbit",
                config=config,
                state=state,
                cwd=git_repo,
            )

    def test_dirty_notice_printed_on_launch(self, git_repo, tmp_path, capsys):
        (git_repo / "dirty.txt").write_text("uncommitted\n")
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            launch(
                branch="feat",
                name="test-dirty",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
        except TmuxError:
            pass  # attachment/switch fails outside a real tmux client
        finally:
            if session_exists("test-dirty"):
                kill_session("test-dirty")

        captured = capsys.readouterr()
        assert "uncommitted changes" in captured.out

    def test_new_branch_branched_from_explicit_base(self, git_repo, tmp_path):
        subprocess.run(
            ["git", "checkout", "-b", "base-branch"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        (git_repo / "base-file.txt").write_text("from base\n")
        subprocess.run(
            ["git", "add", "."], cwd=git_repo, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "base commit"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-"], cwd=git_repo, check=True, capture_output=True
        )

        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            launch(
                branch="new-feature",
                name="test-base-branch",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
                base="base-branch",
            )
        except TmuxError:
            pass  # attachment/switch fails outside a real tmux client
        finally:
            if session_exists("test-base-branch"):
                kill_session("test-base-branch")

        wt_path = git_repo.parent / f"{git_repo.name}.wt" / "test-base-branch"
        assert (wt_path / "base-file.txt").exists()


@pytest.mark.integration
class TestDestroy:
    def test_destroys_tmux_session(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        launch(
            branch="feat",
            name="stop-test",
            config=config,
            state=state,
            cwd=git_repo,
            state_path=state_file,
        )
        assert session_exists("stop-test")

        state2 = load_state(state_file)
        destroy("stop-test", state2, state_file)
        assert not session_exists("stop-test")

    def test_removes_worktree(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        launch(
            branch="feat",
            name="stop-wt",
            config=config,
            state=state,
            cwd=git_repo,
            state_path=state_file,
        )
        worktree_path = git_repo.parent / f"{git_repo.name}.wt" / "stop-wt"
        assert worktree_path.exists()

        state2 = load_state(state_file)
        destroy("stop-wt", state2, state_file)
        assert not worktree_path.exists()

    def test_removes_orbit_from_state(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        launch(
            branch="feat",
            name="stop-state",
            config=config,
            state=state,
            cwd=git_repo,
            state_path=state_file,
        )
        state2 = load_state(state_file)
        destroy("stop-state", state2, state_file)

        state3 = load_state(state_file)
        assert "stop-state" not in state3.orbits

    def test_destroy_nonexistent_orbit_raises(self, tmp_path):
        state = State()
        state_file = tmp_path / "state.json"
        with pytest.raises(Exception, match="No orbit named"):
            destroy("nonexistent", state, state_file)

    def test_destroy_stale_orbit_skips_kill(self, git_repo, tmp_path):
        planet = make_planet(git_repo)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        launch(
            branch="feat",
            name="stale-stop",
            config=config,
            state=state,
            cwd=git_repo,
            state_path=state_file,
        )
        kill_session("stale-stop")

        state2 = load_state(state_file)
        destroy("stale-stop", state2, state_file)

        state3 = load_state(state_file)
        assert "stale-stop" not in state3.orbits
