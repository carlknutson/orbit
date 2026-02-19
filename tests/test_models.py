from datetime import timezone

from orbit.models import Orbit, Pane, Planet


class TestPane:
    def test_defaults(self) -> None:
        pane = Pane(name="shell")
        assert pane.command is None
        assert pane.directory == "."
        assert pane.ports == []

    def test_with_command_and_ports(self) -> None:
        pane = Pane(name="ui", command="npm run dev", ports=[3000])
        assert pane.command == "npm run dev"
        assert pane.ports == [3000]


class TestPlanet:
    def test_slug_from_path(self) -> None:
        planet = Planet(
            name="My App", path="~/projects/myapp", worktree_base="~/planets"
        )
        assert planet.slug == "myapp"

    def test_env_defaults_empty(self) -> None:
        planet = Planet(
            name="My App", path="~/projects/myapp", worktree_base="~/planets"
        )
        assert planet.env == {}

    def test_description_optional(self) -> None:
        planet = Planet(
            name="My App", path="~/projects/myapp", worktree_base="~/planets"
        )
        assert planet.description is None


class TestOrbit:
    def test_defaults(self) -> None:
        orbit = Orbit(
            name="myapp-auth-flow",
            planet="myapp",
            branch="feature/auth-flow",
            worktree="/Users/you/planets/myapp-auth-flow",
            tmux_session="myapp-auth-flow",
        )
        assert orbit.ports == {}
        assert orbit.created_at.tzinfo is not None

    def test_ports_mapping(self) -> None:
        orbit = Orbit(
            name="myapp-main",
            planet="myapp",
            branch="main",
            worktree="/Users/you/planets/myapp-main",
            tmux_session="myapp-main",
            ports={3000: 3001, 5432: 5432},
        )
        assert orbit.ports[3000] == 3001
        assert orbit.ports[5432] == 5432

    def test_created_at_is_utc(self) -> None:
        orbit = Orbit(
            name="myapp-main",
            planet="myapp",
            branch="main",
            worktree="/Users/you/planets/myapp-main",
            tmux_session="myapp-main",
        )
        assert orbit.created_at.tzinfo == timezone.utc
