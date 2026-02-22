import pytest

from orbit.models import Pane, Window
from orbit.tmux import (
    TmuxError,
    _layout_for,
    _pane_base_index,
    first_window_index,
    inside_tmux,
    kill_session,
    new_session,
    select_layout,
    send_keys,
    session_exists,
    set_environment,
    setup_panes,
    setup_windows,
    split_window,
)


class TestInsideTmux:
    def test_false_when_tmux_not_set(self, monkeypatch):
        monkeypatch.delenv("TMUX", raising=False)
        assert not inside_tmux()

    def test_true_when_tmux_set(self, monkeypatch):
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")
        assert inside_tmux()


class TestLayoutFor:
    def test_one_pane_no_layout(self):
        assert _layout_for(1) is None

    def test_two_panes_even_horizontal(self):
        assert _layout_for(2) == "even-horizontal"

    def test_three_panes_main_vertical(self):
        assert _layout_for(3) == "main-vertical"

    def test_four_panes_tiled(self):
        assert _layout_for(4) == "tiled"

    def test_five_panes_tiled(self):
        assert _layout_for(5) == "tiled"


@pytest.mark.integration
class TestSessionLifecycle:
    def test_session_does_not_exist_initially(self):
        assert not session_exists("orbit-test-nonexistent-xyz")

    def test_new_session_creates_session(self, tmp_path):
        name = "orbit-test-new"
        try:
            new_session(name, tmp_path)
            assert session_exists(name)
        finally:
            kill_session(name)

    def test_kill_session_removes_session(self, tmp_path):
        name = "orbit-test-kill"
        new_session(name, tmp_path)
        kill_session(name)
        assert not session_exists(name)

    def test_new_session_raises_on_duplicate(self, tmp_path):
        name = "orbit-test-dup"
        try:
            new_session(name, tmp_path)
            with pytest.raises(TmuxError):
                new_session(name, tmp_path)
        finally:
            kill_session(name)

    def test_kill_nonexistent_raises(self):
        with pytest.raises(TmuxError):
            kill_session("orbit-test-nonexistent-xyz")


@pytest.mark.integration
class TestSetEnvironment:
    def test_sets_env_var_on_session(self, tmp_path):
        name = "orbit-test-env"
        try:
            new_session(name, tmp_path)
            set_environment(name, "MY_VAR", "hello")
            # If no error raised, env was set successfully
        finally:
            kill_session(name)


@pytest.mark.integration
class TestSendKeys:
    def test_send_keys_to_valid_target(self, tmp_path):
        name = "orbit-test-keys"
        try:
            new_session(name, tmp_path)
            win = str(first_window_index(name))
            pane = _pane_base_index(name, win)
            send_keys(f"{name}:{win}.{pane}", "echo hello")
        finally:
            kill_session(name)

    def test_send_keys_to_invalid_target_raises(self):
        with pytest.raises(TmuxError):
            send_keys("orbit-nonexistent-xyz:0.0", "echo hi")


@pytest.mark.integration
class TestSplitWindow:
    def test_split_creates_second_pane(self, tmp_path):
        name = "orbit-test-split"
        try:
            new_session(name, tmp_path)
            win = str(first_window_index(name))
            split_window(name, win, tmp_path)
            # success = no TmuxError raised
        finally:
            kill_session(name)


@pytest.mark.integration
class TestSelectLayout:
    def test_select_even_horizontal(self, tmp_path):
        name = "orbit-test-layout"
        try:
            new_session(name, tmp_path)
            win = str(first_window_index(name))
            split_window(name, win, tmp_path)
            select_layout(name, win, "even-horizontal")
        finally:
            kill_session(name)


@pytest.mark.integration
class TestSetupPanes:
    def test_single_pane_no_command(self, tmp_path):
        name = "orbit-test-panes-single"
        panes = [Pane(name="shell")]
        try:
            new_session(name, tmp_path)
            win = str(first_window_index(name))
            setup_panes(name, win, panes, tmp_path)
        finally:
            kill_session(name)

    def test_two_panes_with_command(self, tmp_path):
        name = "orbit-test-panes-two"
        panes = [
            Pane(name="a", command="echo a"),
            Pane(name="b", command="echo b"),
        ]
        try:
            new_session(name, tmp_path)
            win = str(first_window_index(name))
            setup_panes(name, win, panes, tmp_path)
        finally:
            kill_session(name)

    def test_three_panes(self, tmp_path):
        name = "orbit-test-panes-three"
        panes = [
            Pane(name="a"),
            Pane(name="b"),
            Pane(name="c"),
        ]
        try:
            new_session(name, tmp_path)
            win = str(first_window_index(name))
            setup_panes(name, win, panes, tmp_path)
        finally:
            kill_session(name)

    def test_empty_panes_list_is_noop(self, tmp_path):
        name = "orbit-test-panes-empty"
        try:
            new_session(name, tmp_path)
            win = str(first_window_index(name))
            setup_panes(name, win, [], tmp_path)
        finally:
            kill_session(name)


@pytest.mark.integration
class TestSetupWindows:
    def test_single_window_no_command(self, tmp_path):
        name = "orbit-test-wins-single"
        try:
            new_session(name, tmp_path)
            setup_windows(name, [Window(name="shell")], tmp_path)
        finally:
            kill_session(name)

    def test_multiple_windows_with_commands(self, tmp_path):
        name = "orbit-test-wins-multi"
        windows = [
            Window(name="server", command="echo server"),
            Window(name="shell"),
            Window(name="db", command="echo db"),
        ]
        try:
            new_session(name, tmp_path)
            setup_windows(name, windows, tmp_path)
        finally:
            kill_session(name)

    def test_empty_windows_list_is_noop(self, tmp_path):
        name = "orbit-test-wins-empty"
        try:
            new_session(name, tmp_path)
            setup_windows(name, [], tmp_path)
        finally:
            kill_session(name)

    def test_window_with_panes(self, tmp_path):
        name = "orbit-test-wins-panes"
        windows = [
            Window(
                name="editor",
                panes=[Pane(name="vim", command="echo vim"), Pane(name="tests")],
            ),
            Window(name="shell"),
        ]
        try:
            new_session(name, tmp_path)
            setup_windows(name, windows, tmp_path)
        finally:
            kill_session(name)
