import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from orbit.config import Config
from orbit.models import Orbit, Pane, Planet
from orbit.session import start, stop
from orbit.state import State, load_state
from orbit.tmux import kill_session, session_exists


def make_planet(repo_path: Path, worktree_base: Path, panes=None) -> Planet:
    return Planet(
        name="My App",
        path=str(repo_path),
        worktree_base=str(worktree_base),
        panes=panes or [],
    )


def make_config(planet: Planet) -> Config:
    return Config(planets=[planet])


@pytest.mark.integration
class TestStart:
    def test_creates_tmux_session(self, git_repo, tmp_path):
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        orbit_name = None
        try:
            runner = CliRunner()
            with runner.isolated_filesystem():
                start(
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
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            start(
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
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            start(
                branch="feat",
                name="test-wt",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            assert (tmp_path / "planets" / "test-wt").exists()
        finally:
            if session_exists("test-wt"):
                kill_session("test-wt")

    def test_writes_ports_json(self, git_repo, tmp_path):
        panes = [Pane(name="ui", command="echo hi", ports=[3000])]
        planet = make_planet(git_repo, tmp_path / "planets", panes=panes)
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            start(
                branch="feat",
                name="test-ports",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            ports_file = tmp_path / "planets" / "test-ports" / ".orbit" / "ports.json"
            assert ports_file.exists()
            data = json.loads(ports_file.read_text())
            assert "3000" in data
        finally:
            if session_exists("test-ports"):
                kill_session("test-ports")

    def test_gitignore_has_orbit_entry(self, git_repo, tmp_path):
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            start(
                branch="feat",
                name="test-gi",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            gitignore = tmp_path / "planets" / "test-gi" / ".gitignore"
            assert ".orbit/" in gitignore.read_text().splitlines()
        finally:
            if session_exists("test-gi"):
                kill_session("test-gi")

    def test_collision_with_live_session_raises(self, git_repo, tmp_path):
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        try:
            start(
                branch="feat",
                name="test-coll",
                config=config,
                state=state,
                cwd=git_repo,
                state_path=state_file,
            )
            state2 = load_state(state_file)
            with pytest.raises(Exception, match="already exists"):
                start(
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
        planet = make_planet(git_repo, tmp_path / "planets")
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
            start(
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

    def test_stale_orbit_raises(self, git_repo, tmp_path):
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        stale_orbit = Orbit(
            name="stale-orbit",
            planet=git_repo.name,
            branch="main",
            worktree=str(tmp_path / "planets" / "stale-orbit"),
            tmux_session="stale-orbit",
        )
        state = State()
        state.add(stale_orbit)

        with pytest.raises(Exception, match="stale"):
            start(
                branch="feat",
                name="stale-orbit",
                config=config,
                state=state,
                cwd=git_repo,
            )


@pytest.mark.integration
class TestStop:
    def test_stops_tmux_session(self, git_repo, tmp_path):
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        start(
            branch="feat",
            name="stop-test",
            config=config,
            state=state,
            cwd=git_repo,
            state_path=state_file,
        )
        assert session_exists("stop-test")

        state2 = load_state(state_file)
        stop("stop-test", state2, state_file)
        assert not session_exists("stop-test")

    def test_removes_worktree(self, git_repo, tmp_path):
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        start(
            branch="feat",
            name="stop-wt",
            config=config,
            state=state,
            cwd=git_repo,
            state_path=state_file,
        )
        worktree_path = tmp_path / "planets" / "stop-wt"
        assert worktree_path.exists()

        state2 = load_state(state_file)
        stop("stop-wt", state2, state_file)
        assert not worktree_path.exists()

    def test_removes_orbit_from_state(self, git_repo, tmp_path):
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        start(
            branch="feat",
            name="stop-state",
            config=config,
            state=state,
            cwd=git_repo,
            state_path=state_file,
        )
        state2 = load_state(state_file)
        stop("stop-state", state2, state_file)

        state3 = load_state(state_file)
        assert "stop-state" not in state3.orbits

    def test_stop_nonexistent_orbit_raises(self, tmp_path):
        state = State()
        state_file = tmp_path / "state.json"
        with pytest.raises(Exception, match="No orbit named"):
            stop("nonexistent", state, state_file)

    def test_stop_stale_orbit_skips_kill(self, git_repo, tmp_path):
        planet = make_planet(git_repo, tmp_path / "planets")
        config = make_config(planet)
        state = State()
        state_file = tmp_path / "state.json"

        start(
            branch="feat",
            name="stale-stop",
            config=config,
            state=state,
            cwd=git_repo,
            state_path=state_file,
        )
        kill_session("stale-stop")

        state2 = load_state(state_file)
        stop("stale-stop", state2, state_file)

        state3 = load_state(state_file)
        assert "stale-stop" not in state3.orbits
