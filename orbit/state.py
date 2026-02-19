import json
from pathlib import Path

from pydantic import ValidationError

from orbit.models import Orbit

STATE_PATH = Path("~/.orbit/state.json")


class StateError(Exception):
    pass


class State:
    def __init__(self, orbits: dict[str, Orbit] | None = None) -> None:
        self.orbits: dict[str, Orbit] = orbits or {}

    def add(self, orbit: Orbit) -> None:
        self.orbits[orbit.name] = orbit

    def remove(self, name: str) -> None:
        self.orbits.pop(name, None)

    def get(self, name: str) -> Orbit | None:
        return self.orbits.get(name)

    def all_ports(self) -> set[int]:
        ports: set[int] = set()
        for orbit in self.orbits.values():
            ports.update(orbit.ports.values())
        return ports


def load_state(path: Path | None = None) -> State:
    state_path = (path or STATE_PATH).expanduser()

    if not state_path.exists():
        return State()

    try:
        with open(state_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise StateError(f"Failed to parse state file: {e}") from e

    orbits: dict[str, Orbit] = {}
    for name, orbit_data in data.get("orbits", {}).items():
        try:
            orbits[name] = Orbit(**orbit_data)
        except (ValidationError, TypeError) as e:
            raise StateError(f"Invalid orbit entry '{name}': {e}") from e

    return State(orbits)


def save_state(state: State, path: Path | None = None) -> None:
    state_path = (path or STATE_PATH).expanduser()
    state_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "orbits": {
            name: json.loads(orbit.model_dump_json())
            for name, orbit in state.orbits.items()
        }
    }

    with open(state_path, "w") as f:
        json.dump(data, f, indent=2)
