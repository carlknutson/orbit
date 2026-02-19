import pytest
from click.testing import CliRunner

from orbit.cli import _prompt_select, resolve_name
from orbit.models import Orbit
from orbit.state import State


def make_state(*names: str) -> State:
    state = State()
    for name in names:
        state.add(
            Orbit(
                name=name,
                planet="myapp",
                branch="main",
                worktree=f"/planets/{name}",
                tmux_session=name,
            )
        )
    return state


class TestResolveName:
    def test_explicit_name_returned_directly(self):
        state = make_state("myapp-main", "myapp-feat")
        result = resolve_name("myapp-main", state, prefix_match=False)
        assert result == "myapp-main"

    def test_explicit_name_with_prefix_match_exact(self):
        state = make_state("myapp-main", "myapp-feat")
        result = resolve_name("myapp-main", state, prefix_match=True)
        assert result == "myapp-main"

    def test_prefix_match_resolves_unique(self):
        state = make_state("myapp-main", "myapp-feat")
        result = resolve_name("myapp-m", state, prefix_match=True)
        assert result == "myapp-main"

    def test_prefix_match_no_match_raises(self):
        state = make_state("myapp-main", "myapp-feat")
        import click

        with pytest.raises(click.ClickException, match="No orbit matching"):
            resolve_name("zzz-nonexistent", state, prefix_match=True)

    def test_no_name_single_orbit_returns_it(self, capsys):
        state = make_state("myapp-main")
        result = resolve_name(None, state, prefix_match=False)
        assert result == "myapp-main"

    def test_no_name_no_orbits_raises(self):
        state = State()
        import click

        with pytest.raises(click.ClickException, match="No active orbits"):
            resolve_name(None, state, prefix_match=False)

    def test_no_name_multiple_orbits_prompts(self, monkeypatch):
        state = make_state("myapp-main", "myapp-feat")
        monkeypatch.setattr("click.prompt", lambda *a, **kw: 1)
        result = resolve_name(None, state, prefix_match=False)
        assert result == "myapp-main"

    def test_prefix_match_ambiguous_prompts(self, monkeypatch):
        state = make_state("myapp-main", "myapp-feat")
        monkeypatch.setattr("click.prompt", lambda *a, **kw: 2)
        result = resolve_name("myapp", state, prefix_match=True)
        assert result == "myapp-feat"


class TestPromptSelect:
    def test_valid_selection(self, monkeypatch):
        monkeypatch.setattr("click.prompt", lambda *a, **kw: 2)
        result = _prompt_select(["alpha", "beta", "gamma"])
        assert result == "beta"

    def test_invalid_selection_raises(self, monkeypatch):
        monkeypatch.setattr("click.prompt", lambda *a, **kw: 99)
        import click

        with pytest.raises(click.ClickException, match="Invalid selection"):
            _prompt_select(["alpha", "beta"])


class TestCliCommands:
    def test_help(self):
        from orbit.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Orbit" in result.output

    def test_start_help(self):
        from orbit.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["start", "--help"])
        assert result.exit_code == 0

    def test_attach_help(self):
        from orbit.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["attach", "--help"])
        assert result.exit_code == 0

    def test_switch_help(self):
        from orbit.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["switch", "--help"])
        assert result.exit_code == 0

    def test_list_help(self):
        from orbit.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["list", "--help"])
        assert result.exit_code == 0

    def test_stop_help(self):
        from orbit.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["stop", "--help"])
        assert result.exit_code == 0

    def test_list_no_orbits(self, tmp_path, monkeypatch):
        from orbit.cli import cli

        state_file = tmp_path / "state.json"
        monkeypatch.setattr("orbit.cli.DEFAULT_STATE_PATH", state_file)
        runner = CliRunner()
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "No active orbits" in result.output

    def test_list_shows_orbits(self, tmp_path, monkeypatch):
        from orbit.cli import cli
        from orbit.state import save_state

        state = make_state("myapp-main")
        state_file = tmp_path / "state.json"
        save_state(state, state_file)
        monkeypatch.setattr("orbit.cli.DEFAULT_STATE_PATH", state_file)

        runner = CliRunner()
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "myapp-main" in result.output

    def test_stop_no_orbits_exits_with_error(self, tmp_path, monkeypatch):
        from orbit.cli import cli

        state_file = tmp_path / "state.json"
        monkeypatch.setattr("orbit.cli.DEFAULT_STATE_PATH", state_file)
        runner = CliRunner()
        result = runner.invoke(cli, ["stop"])
        assert result.exit_code != 0

    def test_switch_outside_tmux_exits_with_error(self, tmp_path, monkeypatch):
        from orbit.cli import cli

        state_file = tmp_path / "state.json"
        monkeypatch.setattr("orbit.cli.DEFAULT_STATE_PATH", state_file)
        monkeypatch.delenv("TMUX", raising=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["switch"])
        assert result.exit_code != 0
        assert "tmux" in result.output.lower()
