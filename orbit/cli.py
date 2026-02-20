from pathlib import Path

import click

from orbit.config import Config, ConfigError, ConfigNotice, load_config
from orbit.state import State, StateError, load_state
from orbit.worktree import WorktreeError

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
    from orbit.config import append_planet_to_config, detect_planet, scaffold_planet

    cwd = Path.cwd()
    config = _load_config()

    try:
        detect_planet(cwd, config)
    except ConfigError:
        planet = scaffold_planet(cwd)
        append_planet_to_config(planet, DEFAULT_CONFIG_PATH.expanduser())
        config_path = DEFAULT_CONFIG_PATH.expanduser()
        click.echo(f"Added planet '{planet.name}' to {config_path}.")
        click.echo("Review ~/.orbit/config.yaml and run 'orbit start' again.")
        return

    state = _load_state()
    try:
        session_module.start(
            branch=branch,
            name=name,
            config=config,
            state=state,
            cwd=cwd,
            state_path=DEFAULT_STATE_PATH.expanduser(),
        )
    except WorktreeError as e:
        raise click.ClickException(str(e))


@cli.command("switch")
def switch_cmd() -> None:
    """Pick and switch to an orbit."""
    from orbit import tmux

    if tmux.inside_tmux():
        tmux.choose_session()
        return

    state = _load_state()
    if not state.orbits:
        raise click.ClickException("No active orbits.")
    tmux.attach_and_choose()


@cli.command("list")
def list_cmd() -> None:
    """List all active orbits."""
    from orbit import tmux

    state = _load_state()
    if not state.orbits:
        click.echo("No active orbits.")
        return

    headers = ("ORBIT", "PLANET", "BRANCH", "PORTS", "STATUS")
    rows = []
    for orbit in state.orbits.values():
        status = "running" if tmux.session_exists(orbit.name) else "stale"
        ports_str = ",".join(str(p) for p in orbit.ports.values())
        rows.append((orbit.name, orbit.planet, orbit.branch, ports_str, status))

    widths = [
        max(len(headers[i]), max(len(r[i]) for r in rows))
        for i in range(len(headers) - 1)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    click.echo(fmt.format(*headers[:-1]) + "  " + headers[-1])
    for row in rows:
        click.echo(fmt.format(*row[:-1]) + "  " + row[-1])


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


@cli.command("keys")
def keys_cmd() -> None:
    """Print a tmux cheat sheet for orbit sessions."""
    click.echo(
        "\n"
        "  tmux essentials for orbit\n"
        "\n"
        "  navigating windows\n"
        "    Ctrl-B 1-9            jump to window by number\n"
        "    Ctrl-B n / p          next / previous window\n"
        "\n"
        "  navigating panes\n"
        "    Ctrl-B arrow          move focus to another pane\n"
        "    Ctrl-B z              zoom pane (toggle fullscreen)\n"
        "    Ctrl-B {/}            swap pane positions\n"
        "\n"
        "  scrolling\n"
        "    Ctrl-B [              enter scroll mode (q or Esc to exit)\n"
        "    mouse wheel           scroll (enabled in all orbit sessions)\n"
        "\n"
        "  sessions\n"
        "    Ctrl-B d              detach — orbit keeps running\n"
        "    orbit switch          pick and switch to an orbit\n"
        "    orbit list            see all running orbits\n"
        "\n"
        "  copy / paste\n"
        "    Ctrl-B [              enter copy mode\n"
        "    Space                 start selection\n"
        "    Enter                 copy selection\n"
        "    Ctrl-B ]              paste\n"
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
    except ConfigNotice as e:
        click.echo(str(e))
        raise SystemExit(0)
    except ConfigError as e:
        raise click.ClickException(str(e))


def _load_state() -> State:
    try:
        return load_state(DEFAULT_STATE_PATH.expanduser())
    except StateError as e:
        raise click.ClickException(f"Failed to load state: {e}")
