import pytest

from orbit.config import ConfigError, detect_planet, load_config


class TestLoadConfig:
    def test_loads_valid_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
planets:
  - name: "My App"
    path: "~/projects/myapp"
    worktree_base: "~/planets"
    panes:
      - name: "shell"
        command: null
        directory: "."
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
    worktree_base: "~/planets"
  - name: "App Two"
    path: "~/projects/app2"
    worktree_base: "~/planets"
"""
        )
        config = load_config(config_file)
        assert len(config.planets) == 2
        assert config.planets[0].name == "App One"
        assert config.planets[1].name == "App Two"

    def test_loads_pane_with_ports(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
planets:
  - name: "My App"
    path: "~/projects/myapp"
    worktree_base: "~/planets"
    panes:
      - name: "ui"
        command: "npm run dev"
        directory: "./frontend"
        ports:
          - 3000
"""
        )
        config = load_config(config_file)
        pane = config.planets[0].panes[0]
        assert pane.name == "ui"
        assert pane.command == "npm run dev"
        assert pane.ports == [3000]
        assert pane.directory == "./frontend"

    def test_loads_env(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
planets:
  - name: "My App"
    path: "~/projects/myapp"
    worktree_base: "~/planets"
    env:
      NODE_ENV: "development"
      DEBUG: "true"
"""
        )
        config = load_config(config_file)
        assert config.planets[0].env == {"NODE_ENV": "development", "DEBUG": "true"}

    def test_missing_file_creates_template_and_raises(self, tmp_path):
        config_file = tmp_path / "nonexistent.yaml"
        with pytest.raises(ConfigError, match="add your planets and run again"):
            load_config(config_file)
        assert config_file.exists()
        assert "planets:" in config_file.read_text()

    def test_invalid_yaml_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("planets: [invalid: yaml: content")
        with pytest.raises(ConfigError, match="Failed to parse config"):
            load_config(config_file)

    def test_empty_file_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        with pytest.raises(ConfigError, match="No planets configured"):
            load_config(config_file)

    def test_missing_planets_key_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("other_key: value\n")
        with pytest.raises(ConfigError, match="No planets configured"):
            load_config(config_file)

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
    worktree_base: "{tmp_path}/planets"
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
    worktree_base: "{tmp_path}/planets"
  - name: "App Two"
    path: "{planet2_dir}"
    worktree_base: "{tmp_path}/planets"
"""
        )
        config = load_config(config_file)
        planet = detect_planet(planet1_dir, config)
        assert planet.name == "App One"
