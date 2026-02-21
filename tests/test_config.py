from pathlib import Path

import pytest
import yaml

from orbit.config import (
    ConfigError,
    ConfigNotice,
    append_planet_to_config,
    detect_planet,
    load_config,
    scaffold_planet,
)
from orbit.models import Planet


class TestLoadConfig:
    def test_loads_valid_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
planets:
  - name: "My App"
    path: "~/projects/myapp"
    windows:
      - name: "shell"
"""
        )
        config = load_config(config_file)
        assert len(config.planets) == 1
        assert config.planets[0].name == "My App"

    def test_loads_multiple_planets(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
planets:
  - name: "App One"
    path: "~/projects/app1"
  - name: "App Two"
    path: "~/projects/app2"
"""
        )
        config = load_config(config_file)
        assert len(config.planets) == 2
        assert config.planets[0].name == "App One"
        assert config.planets[1].name == "App Two"

    def test_loads_env(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
planets:
  - name: "My App"
    path: "~/projects/myapp"
    env:
      NODE_ENV: "development"
      DEBUG: "true"
"""
        )
        config = load_config(config_file)
        assert config.planets[0].env == {"NODE_ENV": "development", "DEBUG": "true"}

    def test_missing_file_creates_template_and_raises(self, tmp_path):
        config_file = tmp_path / "nonexistent.yaml"
        with pytest.raises(ConfigNotice, match="add your planets and run again"):
            load_config(config_file)
        assert config_file.exists()
        assert "planets:" in config_file.read_text()

    def test_invalid_yaml_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("planets: [invalid: yaml: content")
        with pytest.raises(ConfigError, match="Failed to parse config"):
            load_config(config_file)

    def test_empty_file_returns_empty_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = load_config(config_file)
        assert config.planets == []

    def test_missing_planets_key_returns_empty_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("other_key: value\n")
        config = load_config(config_file)
        assert config.planets == []

    def test_invalid_planet_schema_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
planets:
  - name: "Missing required fields"
"""
        )
        with pytest.raises(ConfigError, match="Invalid config"):
            load_config(config_file)


class TestDetectPlanet:
    def _make_config(self, tmp_path):
        planet_dir = tmp_path / "myapp"
        planet_dir.mkdir()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"""
planets:
  - name: "My App"
    path: "{planet_dir}"
"""
        )
        return load_config(config_file), planet_dir

    def test_detects_planet_from_root(self, tmp_path):
        config, planet_dir = self._make_config(tmp_path)
        planet = detect_planet(planet_dir, config)
        assert planet.name == "My App"

    def test_detects_planet_from_subdirectory(self, tmp_path):
        config, planet_dir = self._make_config(tmp_path)
        subdir = planet_dir / "src" / "components"
        subdir.mkdir(parents=True)
        planet = detect_planet(subdir, config)
        assert planet.name == "My App"

    def test_raises_when_no_match(self, tmp_path):
        config, _ = self._make_config(tmp_path)
        outside_dir = tmp_path / "other"
        outside_dir.mkdir()
        with pytest.raises(ConfigError, match="not within any configured planet"):
            detect_planet(outside_dir, config)

    def test_error_lists_configured_planets(self, tmp_path):
        config, _ = self._make_config(tmp_path)
        outside_dir = tmp_path / "other"
        outside_dir.mkdir()
        with pytest.raises(ConfigError, match="My App"):
            detect_planet(outside_dir, config)

    def test_detects_first_matching_planet(self, tmp_path):
        planet1_dir = tmp_path / "app1"
        planet1_dir.mkdir()
        planet2_dir = tmp_path / "app2"
        planet2_dir.mkdir()
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            f"""
planets:
  - name: "App One"
    path: "{planet1_dir}"
  - name: "App Two"
    path: "{planet2_dir}"
"""
        )
        config = load_config(config_file)
        planet = detect_planet(planet1_dir, config)
        assert planet.name == "App One"


class TestScaffoldPlanet:
    def test_name_from_directory(self, tmp_path):
        cwd = tmp_path / "ios-shortcuts"
        cwd.mkdir()
        planet = scaffold_planet(cwd)
        assert planet.name == "ios-shortcuts"

    def test_path_relative_to_home(self):
        home = Path.home()
        cwd = home / "projects" / "myapp"
        planet = scaffold_planet(cwd)
        assert planet.path == "~/projects/myapp"

    def test_path_absolute_when_outside_home(self, tmp_path):
        home = Path.home()
        try:
            tmp_path.relative_to(home)
            pytest.skip("tmp_path is under home on this system")
        except ValueError:
            pass
        planet = scaffold_planet(tmp_path)
        assert planet.path == str(tmp_path)


class TestAppendPlanetToConfig:
    def test_appended_content_is_valid_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("planets:\n")
        planet = Planet(name="myapp", path="~/projects/myapp")
        append_planet_to_config(planet, config_file)
        data = yaml.safe_load(config_file.read_text())
        assert len(data["planets"]) == 1
        assert data["planets"][0]["name"] == "myapp"

    def test_appends_preserving_existing(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "planets:\n  - name: existing\n    path: ~/projects/existing\n"
        )
        planet = Planet(name="myapp", path="~/projects/myapp")
        append_planet_to_config(planet, config_file)
        data = yaml.safe_load(config_file.read_text())
        assert len(data["planets"]) == 2
        names = [p["name"] for p in data["planets"]]
        assert "existing" in names
        assert "myapp" in names
