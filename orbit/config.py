from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from orbit.models import Planet

CONFIG_PATH = Path("~/.orbit/config.yaml")


class ConfigError(Exception):
    pass


class Config(BaseModel):
    planets: list[Planet]


DEFAULT_CONFIG_TEMPLATE = """\
# Orbit configuration
# Add one entry per project (planet) you want to manage.

planets:
  # - name: myproject
  #   path: ~/projects/myproject
  #   worktree_base: ~/orbits/myproject
  #   panes:
  #     - name: server
  #       command: npm run dev
  #       ports: [3000]
"""


def load_config(path: Path | None = None) -> Config:
    config_path = (path or CONFIG_PATH).expanduser()

    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
        raise ConfigError(f"Created {config_path} — add your planets and run again.")

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse config: {e}") from e

    if not data or "planets" not in data:
        raise ConfigError(f"No planets configured in {config_path}")

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
