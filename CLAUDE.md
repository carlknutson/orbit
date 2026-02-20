# Orbit — Development Guide

## Stack

- **Language:** Python 3.10+
- **Package manager:** uv
- **CLI framework:** Click
- **Validation:** Pydantic
- **Linting/formatting:** ruff
- **Type checking:** mypy
- **Tests:** pytest

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run orbit

# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy .
```

## Testing Philosophy

Orbit's behavior is mostly side effects (tmux sessions, git worktrees, port binding, filesystem state) — mocking subprocess calls tells you little. Prefer integration tests that exercise real behavior.

**Integration tests** (majority):
- Test whole commands against a real but temporary environment
- Use `pytest`'s `tmp_path` fixture for throwaway git repos and state files
- Assume tmux is available locally
- Mark with `@pytest.mark.integration` to allow skipping in CI if needed

**Unit tests** (pure logic only):
- Branch slug sanitization
- Port assignment algorithm
- Name resolution logic

**CI escape hatch:** when CI is added, use `-m "not integration"` to skip tmux-dependent tests or run in a tmux-capable container. No restructuring needed.

## Workflow Rules

- **Run tests after changes.** Run `uv run pytest` before considering a task done.
- **Run linter after changes.** Run `uv run ruff check .` and `uv run ruff format .` after making changes.
- **No speculative changes.** Only make changes that were explicitly requested — no drive-by refactors, added comments, or extra features.

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/). Format:

```
<type>(<scope>): <description>

[optional body]
```

**Types:** `feat`, `fix`, `chore`, `refactor`, `test`, `docs`

**Scope:** the module name (e.g. `config`, `ports`, `cli`)

**Examples:**
```
feat(config): add planet detection from CWD
fix(ports): handle socket probe failure on restricted ports
test(state): add integration tests for state read/write
chore: add pyproject.toml and package scaffolding
```

- Description is lowercase, no trailing period
- Body is optional — use it for non-obvious reasoning, not to restate the diff

## Build Sequence

Work through these in order. Each step builds on the previous.

1. **Project scaffolding** — `pyproject.toml`, package structure, empty module stubs
2. **Models** — Pydantic models (`Planet`, `Pane`, `Orbit`)
3. **Config** — parse/validate `~/.orbit/config.yaml`
   - ✅ Test + commit
4. **State** — read/write `~/.orbit/state.json`
   - ✅ Test + commit
5. **Ports** — port assignment algorithm
   - ✅ Test + commit
6. **Worktree** — git subprocess calls
7. **Tmux** — tmux subprocess wrapper
8. **Session** — orbit lifecycle, ties everything together
   - ✅ Test + commit
9. **CLI** — Click commands, name resolution, output formatting
   - ✅ Test + commit

Remove this section once the implementation is complete.

## Future

Features intentionally deferred — pick these up when the time is right:

- **Pane config per window** — `Window` currently supports only a single `command`. The natural next step is `panes: list[Pane]` on `Window`, letting users define split layouts per window (e.g. editor + test runner side by side). The `Pane` model and `setup_panes` logic in `tmux.py` already exist as a foundation; the main work is wiring them into `setup_windows` and updating the config schema.

## Project Structure

```
orbit/
├── __init__.py
├── cli.py        # Click entry point and command definitions
├── config.py     # ~/.orbit/config.yaml parsing & validation
├── session.py    # Orbit creation & lifecycle
├── tmux.py       # Tmux subprocess wrapper
├── worktree.py   # Git worktree management
├── state.py      # State persistence
├── ports.py      # Port assignment logic
└── models.py     # Pydantic models (Planet, Orbit, Pane)

pyproject.toml    # uv project config; `orbit` script entry point
tests/            # pytest test suite
```
