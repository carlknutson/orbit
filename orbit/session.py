from pathlib import Path

import click

from orbit import tmux, worktree
from orbit.config import Config, detect_planet
from orbit.models import Orbit
from orbit.state import State, save_state
from orbit.worktree import WorktreeError


def launch(
    branch: str | None,
    name: str | None,
    config: Config,
    state: State,
    cwd: Path,
    state_path: Path | None = None,
    base: str | None = None,
) -> None:
    planet = detect_planet(cwd, config)

    if branch is None:
        branch = worktree.detect_branch(cwd)

    remote, remote_notice = worktree.choose_remote(cwd)
    if remote_notice:
        click.echo(remote_notice)

    branch_slug = worktree.slugify(branch)

    if name is not None:
        orbit_name = name
        existing = state.get(orbit_name)
        if existing is not None:
            if tmux.session_exists(orbit_name):
                raise click.ClickException(
                    f"An orbit named '{orbit_name}' already exists. "
                    f"Use a different --name, "
                    f"or 'orbit destroy {orbit_name}' to tear it down first."
                )
            else:
                raise click.ClickException(
                    f"An orbit named '{orbit_name}' exists but its tmux session is no "
                    f"longer live (stale). "
                    f"Run 'orbit destroy {orbit_name}' to clean it up first."
                )
    else:
        orbit_name = branch_slug
        if state.get(orbit_name) is not None:
            n = 2
            while state.get(f"{branch_slug}-{n}") is not None:
                n += 1
            orbit_name = f"{branch_slug}-{n}"

    planet_dir = Path(planet.path).expanduser()
    worktree_base = planet_dir.parent / f"{planet_dir.name}.wt"
    worktree_path = worktree_base / orbit_name
    worktree_base.mkdir(parents=True, exist_ok=True)

    if worktree.has_uncommitted_changes(cwd):
        click.echo(
            "Note: working tree has uncommitted changes (not transferred to worktree)"
        )

    is_new_branch = not worktree.branch_exists_locally(cwd, branch) and not (
        remote and worktree.remote_branch_exists(cwd, remote, branch)
    )

    if is_new_branch and base is None and remote is not None:
        base = worktree.detect_default_branch(cwd, remote)

    if is_new_branch and base is not None:
        click.echo(f"Branching '{branch}' from '{base}'")

    worktree.create_worktree(cwd, worktree_path, branch, remote, base=base)

    patterns = planet.sync_untracked
    if patterns is None:
        patterns = [".*"]
    if patterns:
        synced = worktree.sync_untracked_to_worktree(
            Path(planet.path).expanduser(),
            worktree_path,
            patterns,
        )
        if synced:
            click.echo(f"Synced {len(synced)} untracked path(s) into worktree")

    tmux.new_session(orbit_name, worktree_path)

    tmux.set_option(orbit_name, "mouse", "on")
    tmux.set_option(orbit_name, "status-left", f" {orbit_name} ")
    tmux.set_option(orbit_name, "status-right", f" {branch} ")

    for key, value in planet.env.items():
        tmux.set_environment(orbit_name, key, value)
    tmux.set_environment(orbit_name, "CLAUDE_CODE_TASK_LIST_ID", orbit_name)

    tmux.setup_windows(orbit_name, planet.windows, worktree_path)

    orbit = Orbit(
        name=orbit_name,
        planet=planet.slug,
        branch=branch,
        worktree=str(worktree_path),
        tmux_session=orbit_name,
    )
    state.add(orbit)
    save_state(state, state_path)

    click.echo(f"\nLaunched {orbit_name}\n")

    if tmux.inside_tmux():
        tmux.switch_client(orbit_name)
    else:
        tmux.attach_session(orbit_name)


def destroy(
    orbit_name: str,
    state: State,
    state_path: Path | None = None,
) -> None:
    orbit = state.get(orbit_name)
    if orbit is None:
        raise click.ClickException(f"No orbit named '{orbit_name}' found.")

    if tmux.session_exists(orbit_name):
        tmux.kill_session(orbit_name)

    worktree_path = Path(orbit.worktree)
    if worktree_path.exists():
        if worktree.has_uncommitted_changes(worktree_path):
            click.confirm(
                f"Worktree at {worktree_path} has uncommitted changes. Remove anyway?",
                abort=True,
            )
        try:
            main_repo = worktree.get_main_repo_path(worktree_path)
            worktree.remove_worktree(main_repo, worktree_path)
        except WorktreeError as e:
            click.echo(f"Warning: failed to remove worktree: {e}")
    else:
        click.echo(f"Worktree directory {worktree_path} not found; skipping removal.")

    state.remove(orbit_name)
    save_state(state, state_path)
    click.echo(f"Destroyed {orbit_name}")
