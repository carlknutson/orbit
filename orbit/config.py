from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from orbit.models import Planet

CONFIG_PATH = Path("~/.orbit/config.yaml")


class ConfigError(Exception):
    pass


class ConfigNotice(Exception):
    """Raised for expected situations that need user action but are not errors."""

    pass


class Config(BaseModel):
    planets: list[Planet]


DEFAULT_CONFIG_TEMPLATE = """\
# Orbit configuration
# Add one entry per project (planet) you want to manage.
#
# Each planet has one or more windows. Windows come in two forms:
#
#   Single-pane window (use `command` directly on the window):
#
#     windows:
#       - name: server
#         command: npm run dev
#
#   Multi-pane window (use `panes` for a split layout):
#
#     windows:
#       - name: dev
#         panes:
#           - name: editor
#             command: vim .
#           - name: tests
#             command: pytest --watch
#             directory: ./backend   # optional — relative to worktree root
#
# You can mix both styles across windows in the same planet.

planets:
  # - name: myproject
  #   path: ~/projects/myproject    # worktrees are created as siblings
  #   env:                          # optional environment variables
  #     NODE_ENV: development
  #   windows:
  #     - name: server              # single-pane: just a command
  #       command: npm run dev
  #     - name: dev                 # multi-pane: split layout
  #       panes:
  #         - name: editor
  #           command: vim .
  #         - name: tests
  #           command: pytest --watch
  #     - name: shell               # empty window — no command, just a shell
"""


def load_config(path: Path | None = None) -> Config:
    config_path = (path or CONFIG_PATH).expanduser()

    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
        raise ConfigNotice(f"Created {config_path} — add your planets and run again.")

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse config: {e}") from e

    data = data or {}
    if not data.get("planets"):
        data["planets"] = []

    try:
        return Config(**data)
    except ValidationError as e:
        raise ConfigError(f"Invalid config: {e}") from e


def detect_planet(cwd: Path, config: Config) -> Planet:
    resolved_cwd = cwd.resolve()
    for planet in config.planets:
        planet_path = Path(planet.path).expanduser().resolve()
        try:
            resolved_cwd.relative_to(planet_path)
            return planet
        except ValueError:
            continue

    configured = "\n".join(f"  - {p.name} ({p.path})" for p in config.planets)
    raise ConfigError(
        f"Current directory is not within any configured planet.\n"
        f"Configured planets:\n{configured}"
    )


def scaffold_planet(cwd: Path) -> Planet:
    name = cwd.name
    home = Path.home()
    try:
        rel = cwd.relative_to(home)
        path = f"~/{rel}"
    except ValueError:
        path = str(cwd)
    return Planet(name=name, path=path)


def append_planet_to_config(planet: Planet, config_path: Path) -> None:
    snippet = f"\n  - name: {planet.name}\n    path: {planet.path}\n"
    with open(config_path, "a") as f:
        f.write(snippet)
