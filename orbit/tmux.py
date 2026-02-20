import os
import subprocess
from pathlib import Path

from orbit.models import Pane, Window


class TmuxError(Exception):
    pass


def inside_tmux() -> bool:
    return bool(os.environ.get("TMUX"))


def session_exists(name: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", name],
        capture_output=True,
    )
    return result.returncode == 0


def new_session(name: str, start_dir: Path) -> None:
    result = subprocess.run(
        ["tmux", "new-session", "-d", "-s", name, "-c", str(start_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(f"Failed to create session '{name}': {result.stderr.strip()}")


def kill_session(name: str) -> None:
    result = subprocess.run(
        ["tmux", "kill-session", "-t", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(f"Failed to kill session '{name}': {result.stderr.strip()}")


def set_environment(session: str, key: str, value: str) -> None:
    result = subprocess.run(
        ["tmux", "set-environment", "-t", session, key, value],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(f"Failed to set environment: {result.stderr.strip()}")


def set_option(session: str, option: str, value: str) -> None:
    result = subprocess.run(
        ["tmux", "set-option", "-t", session, option, value],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip())


def set_window_option(session: str, option: str, value: str) -> None:
    result = subprocess.run(
        ["tmux", "set-window-option", "-t", f"{session}:0", option, value],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip())


def set_pane_title(target: str, title: str) -> None:
    result = subprocess.run(
        ["tmux", "select-pane", "-t", target, "-T", title],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip())


def send_keys(target: str, command: str) -> None:
    result = subprocess.run(
        ["tmux", "send-keys", "-t", target, command, "Enter"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(f"Failed to send keys to '{target}': {result.stderr.strip()}")


def split_window(session: str, start_dir: Path) -> None:
    result = subprocess.run(
        ["tmux", "split-window", "-t", f"{session}:0", "-c", str(start_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(f"Failed to split window: {result.stderr.strip()}")


def select_layout(session: str, layout: str) -> None:
    result = subprocess.run(
        ["tmux", "select-layout", "-t", f"{session}:0", layout],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(f"Failed to select layout: {result.stderr.strip()}")


def choose_session() -> None:
    result = subprocess.run(
        ["tmux", "choose-tree", "-s"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip())


def switch_client(name: str) -> None:
    result = subprocess.run(
        ["tmux", "switch-client", "-t", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(f"Failed to switch client to '{name}': {result.stderr.strip()}")


def attach_session(name: str) -> None:
    os.execvp("tmux", ["tmux", "attach-session", "-t", name])


def attach_and_choose() -> None:
    os.execvp("tmux", ["tmux", "attach-session", ";", "choose-tree", "-s"])


def _layout_for(n: int) -> str | None:
    if n <= 1:
        return None
    if n == 2:
        return "even-horizontal"
    if n == 3:
        return "main-vertical"
    return "tiled"


def setup_panes(session: str, panes: list[Pane], worktree_path: Path) -> None:
    if not panes:
        return

    for pane in panes[1:]:
        pane_dir = worktree_path / pane.directory
        split_window(session, pane_dir)

    layout = _layout_for(len(panes))
    if layout:
        select_layout(session, layout)

    if len(panes) > 1:
        set_window_option(session, "pane-border-status", "top")
        set_window_option(session, "pane-border-format", " #{pane_title} ")

    for i, pane in enumerate(panes):
        set_pane_title(f"{session}:0.{i}", pane.name)
        if pane.command is not None:
            send_keys(f"{session}:0.{i}", pane.command)


def rename_window(session: str, index: int, name: str) -> None:
    result = subprocess.run(
        ["tmux", "rename-window", "-t", f"{session}:{index}", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip())


def new_window(session: str, name: str, start_dir: Path) -> None:
    result = subprocess.run(
        ["tmux", "new-window", "-t", session, "-n", name, "-c", str(start_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip())


def select_window(session: str, index: int) -> None:
    result = subprocess.run(
        ["tmux", "select-window", "-t", f"{session}:{index}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TmuxError(result.stderr.strip())


def setup_windows(session: str, windows: list[Window], worktree_path: Path) -> None:
    if not windows:
        return

    rename_window(session, 0, windows[0].name)
    if windows[0].command:
        send_keys(f"{session}:{windows[0].name}", windows[0].command)

    for window in windows[1:]:
        new_window(session, window.name, worktree_path)
        if window.command:
            send_keys(f"{session}:{window.name}", window.command)

    select_window(session, 0)
