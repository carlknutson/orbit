from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from orbit.models import Planet

CONFIG_PATH = Path("~/.orbit/config.yaml")


class ConfigError(Exception):
    pass


class Config(BaseModel):
    planets: list[Planet]


def load_config(path: Path | None = None) -> Config:
    config_path = (path or CONFIG_PATH).expanduser()

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

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
