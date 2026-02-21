import json

import pytest

from orbit.models import Orbit
from orbit.state import State, StateError, load_state, save_state


def make_orbit(name: str = "myapp-main", **kwargs) -> Orbit:
    defaults = dict(
        name=name,
        planet="myapp",
        branch="main",
        worktree=f"/planets/{name}",
        tmux_session=name,
    )
    defaults.update(kwargs)
    return Orbit(**defaults)


class TestState:
    def test_empty_by_default(self):
        state = State()
        assert state.orbits == {}

    def test_add_orbit(self):
        state = State()
        orbit = make_orbit()
        state.add(orbit)
        assert state.orbits["myapp-main"] is orbit

    def test_remove_orbit(self):
        state = State()
        orbit = make_orbit()
        state.add(orbit)
        state.remove("myapp-main")
        assert "myapp-main" not in state.orbits

    def test_remove_missing_is_noop(self):
        state = State()
        state.remove("nonexistent")  # should not raise

    def test_get_returns_orbit(self):
        state = State()
        orbit = make_orbit()
        state.add(orbit)
        assert state.get("myapp-main") is orbit

    def test_get_returns_none_for_missing(self):
        state = State()
        assert state.get("nonexistent") is None


class TestLoadState:
    def test_returns_empty_state_when_file_missing(self, tmp_path):
        state = load_state(tmp_path / "state.json")
        assert state.orbits == {}

    def test_loads_orbits_from_file(self, tmp_path):
        state_file = tmp_path / "state.json"
        orbit = make_orbit()
        state_file.write_text(
            json.dumps({"orbits": {"myapp-main": json.loads(orbit.model_dump_json())}})
        )
        state = load_state(state_file)
        assert "myapp-main" in state.orbits

    def test_invalid_json_raises(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text("not valid json{")
        with pytest.raises(StateError, match="Failed to parse state file"):
            load_state(state_file)

    def test_invalid_orbit_schema_raises(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(
            json.dumps({"orbits": {"myapp-main": {"name": "myapp-main"}}})
        )
        with pytest.raises(StateError, match="Invalid orbit entry"):
            load_state(state_file)

    def test_empty_orbits_object(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"orbits": {}}))
        state = load_state(state_file)
        assert state.orbits == {}


class TestSaveState:
    def test_saves_and_reloads(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = State()
        state.add(make_orbit())
        save_state(state, state_file)

        loaded = load_state(state_file)
        assert "myapp-main" in loaded.orbits

    def test_creates_parent_directory(self, tmp_path):
        state_file = tmp_path / "nested" / "dir" / "state.json"
        save_state(State(), state_file)
        assert state_file.exists()

    def test_overwrites_existing(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = State()
        state.add(make_orbit("myapp-main"))
        save_state(state, state_file)

        state2 = State()
        state2.add(make_orbit("myapp-feat"))
        save_state(state2, state_file)

        loaded = load_state(state_file)
        assert "myapp-feat" in loaded.orbits
        assert "myapp-main" not in loaded.orbits

    def test_saves_valid_json(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = State()
        state.add(make_orbit())
        save_state(state, state_file)

        with open(state_file) as f:
            data = json.load(f)
        assert "orbits" in data
        assert "myapp-main" in data["orbits"]

    def test_roundtrip_preserves_branch(self, tmp_path):
        state_file = tmp_path / "state.json"
        state = State()
        state.add(make_orbit(branch="feature/auth-flow"))
        save_state(state, state_file)

        loaded = load_state(state_file)
        assert loaded.orbits["myapp-main"].branch == "feature/auth-flow"
