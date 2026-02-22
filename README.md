# orbit

CLI tool for isolated, tmux-based development environments — one per branch, each with its own worktree, running simultaneously.

## First run

Run `orbit` from any repo. Orbit detects the project, adds it to config, and opens your editor so you can review before anything is created. No YAML required upfront to try it.

## Usage

```bash
orbit [branch]          # launch an orbit for the current project; --from <base> to set the base branch
orbit jump              # pick and attach to an orbit (works inside or outside tmux)
orbit list              # list all active orbits with status
orbit destroy [name]    # tear down an orbit and remove its worktree
orbit config            # open ~/.orbit/config.yaml in $EDITOR
orbit keys              # print a tmux cheat sheet for orbit sessions
```

## Configuration

`~/.orbit/config.yaml` — one entry per project:

```yaml
planets:
  - name: myproject
    path: ~/projects/myproject
    env:                        # optional environment variables
      NODE_ENV: development
    windows:
      - name: server            # single-pane: just a command
        command: npm run dev
      - name: dev               # multi-pane: split layout
        panes:
          - name: editor
            command: vim .
          - name: tests
            command: pytest --watch
      - name: shell             # empty window — just a shell
```

Worktrees are created automatically as siblings of `path` (e.g. `~/projects/myproject.wt/my-branch`). No extra config needed.

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
