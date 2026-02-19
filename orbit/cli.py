from pathlib import Path

import click

from orbit.config import Config, ConfigError, load_config
from orbit.state import State, StateError, load_state

DEFAULT_CONFIG_PATH = Path("~/.orbit/config.yaml")
DEFAULT_STATE_PATH = Path("~/.orbit/state.json")


@click.group()
def cli() -> None:
    """Orbit — parallel local development environments."""


@cli.command()
@click.argument("branch", required=False)
@click.option("--name", "-n", help="Override the orbit name")
def start(branch: str | None, name: str | None) -> None:
    """Create a new orbit for the current planet."""
    from orbit import session as session_module

    config = _load_config()
    state = _load_state()
    session_module.start(
        branch=branch,
        name=name,
        config=config,
        state=state,
        cwd=Path.cwd(),
        state_path=DEFAULT_STATE_PATH.expanduser(),
    )


@cli.command()
@click.argument("name", required=False)
def attach(name: str | None) -> None:
    """Attach to a running orbit's tmux session."""
    from orbit import tmux

    state = _load_state()
    orbit_name = resolve_name(name, state, prefix_match=False)
    if tmux.inside_tmux():
        click.echo(
            "You are inside a tmux session. "
            "Use 'orbit switch' to jump between orbits without nesting sessions."
        )
    tmux.attach_session(orbit_name)


@cli.command("switch")
@click.argument("name", required=False)
def switch_cmd(name: str | None) -> None:
    """Switch to another orbit (from inside tmux)."""
    from orbit import tmux

    if not tmux.inside_tmux():
        raise click.ClickException(
            "Not inside a tmux session. Use 'orbit attach' instead."
        )
    state = _load_state()
    orbit_name = resolve_name(name, state, prefix_match=True)
    tmux.switch_client(orbit_name)


@cli.command("list")
def list_cmd() -> None:
    """List all active orbits."""
    from orbit import tmux

    state = _load_state()
    if not state.orbits:
        click.echo("No active orbits.")
        return

    click.echo(f"{'ORBIT':<20} {'PLANET':<10} {'BRANCH':<20} {'PORTS':<20} STATUS")
    for orbit in state.orbits.values():
        status = "running" if tmux.session_exists(orbit.name) else "stale"
        ports_str = ",".join(str(p) for p in orbit.ports.values())
        line = (
            f"{orbit.name:<20} {orbit.planet:<10} "
            f"{orbit.branch:<20} {ports_str:<20} {status}"
        )
        click.echo(line)


@cli.command()
@click.argument("name", required=False)
def stop(name: str | None) -> None:
    """Stop an orbit and clean up its worktree."""
    from orbit import session as session_module

    state = _load_state()
    orbit_name = resolve_name(name, state, prefix_match=False)
    session_module.stop(
        orbit_name=orbit_name,
        state=state,
        state_path=DEFAULT_STATE_PATH.expanduser(),
    )


def resolve_name(name: str | None, state: State, prefix_match: bool) -> str:
    orbits = list(state.orbits.keys())

    if name is not None:
        if prefix_match:
            matches = [n for n in orbits if n.startswith(name)]
            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                return _prompt_select(matches)
            else:
                raise click.ClickException(f"No orbit matching '{name}' found.")
        return name

    if not orbits:
        raise click.ClickException("No active orbits.")
    if len(orbits) == 1:
        click.echo(f"Acting on: {orbits[0]}")
        return orbits[0]
    return _prompt_select(orbits)


def _prompt_select(orbits: list[str]) -> str:
    click.echo("Multiple orbits active:")
    for i, name in enumerate(orbits, 1):
        click.echo(f"  {i}. {name}")
    idx: int = click.prompt("Select orbit", type=int)
    if 1 <= idx <= len(orbits):
        return orbits[idx - 1]
    raise click.ClickException("Invalid selection.")


def _load_config() -> Config:
    try:
        return load_config()
    except ConfigError as e:
        raise click.ClickException(str(e))


def _load_state() -> State:
    try:
        return load_state(DEFAULT_STATE_PATH.expanduser())
    except StateError as e:
        raise click.ClickException(f"Failed to load state: {e}")
