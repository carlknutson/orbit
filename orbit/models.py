from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class Pane(BaseModel):
    name: str
    command: str | None = None
    directory: str = "."
    ports: list[int] = Field(default_factory=list)


class Window(BaseModel):
    name: str
    command: str | None = None
    ports: list[int] = Field(default_factory=list)
    panes: list[Pane] = Field(default_factory=list)


class Planet(BaseModel):
    name: str
    path: str
    description: str | None = None
    worktree_base: str
    env: dict[str, str] = Field(default_factory=dict)
    windows: list[Window] = Field(default_factory=list)

    @property
    def slug(self) -> str:
        return Path(self.path).expanduser().name


class Orbit(BaseModel):
    name: str
    planet: str
    branch: str
    worktree: str
    tmux_session: str
    ports: dict[int, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
