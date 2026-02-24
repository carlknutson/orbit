from datetime import timezone

from orbit.models import Orbit, Pane, Planet, Window


class TestPane:
    def test_defaults(self) -> None:
        pane = Pane(name="shell")
        assert pane.command is None
        assert pane.directory == "."

    def test_with_command(self) -> None:
        pane = Pane(name="ui", command="npm run dev")
        assert pane.command == "npm run dev"


class TestWindow:
    def test_defaults(self) -> None:
        window = Window(name="shell")
        assert window.command is None

    def test_with_command(self) -> None:
        window = Window(name="server", command="npm run dev")
        assert window.command == "npm run dev"

    def test_window_with_panes(self) -> None:
        window = Window(name="editor", panes=[Pane(name="vim"), Pane(name="tests")])
        assert len(window.panes) == 2
        assert window.command is None


class TestPlanet:
    def test_slug_from_path(self) -> None:
        planet = Planet(name="My App", path="~/projects/myapp")
        assert planet.slug == "myapp"

    def test_env_defaults_empty(self) -> None:
        planet = Planet(name="My App", path="~/projects/myapp")
        assert planet.env == {}

    def test_description_optional(self) -> None:
        planet = Planet(name="My App", path="~/projects/myapp")
        assert planet.description is None

    def test_sync_untracked_defaults_to_none(self) -> None:
        planet = Planet(name="My App", path="~/projects/myapp")
        assert planet.sync_untracked is None

    def test_sync_untracked_accepts_list(self) -> None:
        planet = Planet(name="My App", path="~/projects/myapp", sync_untracked=[".env"])
        assert planet.sync_untracked == [".env"]


class TestOrbit:
    def test_defaults(self) -> None:
        orbit = Orbit(
            name="myapp-auth-flow",
            planet="myapp",
            branch="feature/auth-flow",
            worktree="/Users/you/projects/myapp/.worktrees/myapp-auth-flow",
            tmux_session="myapp-auth-flow",
        )
        assert orbit.created_at.tzinfo is not None

    def test_created_at_is_utc(self) -> None:
        orbit = Orbit(
            name="myapp-main",
            planet="myapp",
            branch="main",
            worktree="/Users/you/projects/myapp/.worktrees/myapp-main",
            tmux_session="myapp-main",
        )
        assert orbit.created_at.tzinfo == timezone.utc
