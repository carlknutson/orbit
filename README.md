# orbit
CLI tool for managing tmux-based development workspaces — start, switch, and track feature contexts with a single command.

## Installation

Install globally as a uv tool so `orbit` is available in any repo:

```bash
uv tool install --editable /path/to/orbit
```

The `--editable` flag means source changes take effect immediately without reinstalling.

Verify it's installed:

```bash
uv tool list
which orbit
```

Uninstall:

```bash
uv tool uninstall orbit
```

## Development

```bash
# Install dependencies
uv sync

# Run the CLI locally
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

## Configuration

On first run, orbit creates `~/.orbit/config.yaml` with a commented template. Edit it to add your projects:

```yaml
planets:
  - name: myproject
    path: ~/projects/myproject
    worktree_base: ~/orbits/myproject
    panes:
      - name: server
        command: npm run dev
        ports: [3000]
```
