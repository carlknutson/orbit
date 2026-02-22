# Orbit — Feature Overview

**Version:** 0.1.0 | **Status:** Implementation Ready

Orbit is a CLI tool for spinning up isolated local development environments that run in parallel without interfering with each other. Each environment — an **orbit** — is a git worktree, its running services, and its claimed ports, all managed as a unit. The core problem it solves: working across multiple branches, features, or projects simultaneously without port conflicts or context-switching overhead.

---

## Core Concepts

- **Orbit** — A fully isolated development environment: one git worktree + its running panes + its claimed ports. Multiple orbits can run simultaneously across branches and planets (codebases). Each orbit has a unique **name** that is its identity across all commands.
- **Orbit name** — The stable identifier for an orbit. Defaults to `{planet_slug}-{branch_slug}` (e.g. `myapp-auth-flow`), but can be overridden on `orbit launch` via `--name`. This name is the tmux session name, the state key, and the argument accepted by all other commands.
- **Planet** — A codebase registered in `~/.orbit/config.yaml` with its path, pane definitions, and port declarations.
- **Planet slug** — The basename of the planet's `path` (e.g. `~/projects/myapp` → `myapp`). Used in default orbit names and worktree paths. If two planets share a basename, the slug suffix is assigned by YAML array index at first use and stored in state — reordering the config YAML will not silently rename existing orbits (e.g. `myapp`, `myapp-2`).
- **Pane** — A tmux pane running a specific process within an orbit (e.g. docker, ui server, shell).
- **Branch** — The git branch an orbit's worktree is checked out on. Stored as metadata — not the orbit's identity.
- **State** — Orbit's runtime registry of active orbits, stored in `~/.orbit/state.json`. Separate from config — tracks what is currently running, not what is configured.

Each orbit is a **single tmux window with multiple panes** laid out in a grid. The tmux session name is the orbit name (e.g. `myapp-auth-flow`). The worktree is checked out at `{worktree_base}/{orbit_name}` (e.g. `~/planets/myapp-auth-flow`).

---

## CLI Commands

| Command | Description |
|---|---|
| `orbit launch [branch] [--name <name>]` | Creates worktree, starts all panes, and claims ports |
| `orbit attach [name]` | Attaches to a running orbit's tmux session (from outside tmux) |
| `orbit jump [name]` | Switches the active tmux client to another orbit (from inside tmux) |
| `orbit list` | Lists all active orbits |
| `orbit destroy [name]` | Kills the orbit, releases ports, and removes the worktree |

`orbit launch` is the only command that requires CWD to be within a planet's directory — it needs to detect the planet and git repository. All other commands operate on orbit names and work from any directory.

**Name resolution** for `orbit attach`, `orbit jump`, and `orbit destroy`:
- If a name is provided, use it directly
- If omitted and one orbit is active: act on it, printing which one
- If omitted and multiple orbits are active: show a numbered prompt listing orbit names
- If omitted and no orbits are active: exit with an error

Prefix matching (resolving a partial name to the full orbit name) is supported only by `orbit jump`. `orbit attach` and `orbit destroy` require an exact orbit name.

---

## Configuration (`~/.orbit/config.yaml`)

A single personal config file listing all registered planets. Never lives in a codebase repo — this is per-user. Orbit expects this file to exist; if it is empty or missing planets, commands that require a planet will fail with a clear error.

```yaml
planets:
  - name: "My App"
    path: "~/projects/myapp"
    description: "React + Django stack"
    worktree_base: "~/planets"    # where worktrees are checked out

    env:
      NODE_ENV: "development"

    panes:
      - name: "docker"
        command: "docker-compose up"
        directory: "."
        ports:
          - 5432
          - 6379
      - name: "ui"
        command: "npm run dev"
        directory: "./frontend"
        ports:
          - 3000
      - name: "shell"
        command: null              # interactive shell
        directory: "."

  - name: "API Service"
    path: "~/projects/api"
    worktree_base: "~/planets"
    panes:
      - name: "server"
        command: "python manage.py runserver"
        ports:
          - 8000
      - name: "shell"
        command: null
        directory: "."
```

- `ports` declares the standard dev ports a pane uses locally. Orbit uses these as the starting point for port assignment on `orbit launch` — assigning the same port if free, or the next unclaimed one if not.
- `directory` values are relative to the orbit's worktree root.
- `env` values are injected into all panes of the orbit via `tmux set-environment`, called before any panes are created so all panes inherit the values.

---

## Planet Detection

`orbit launch` detects the planet by matching CWD against each planet's `path` in config (including subdirectories). If the CWD does not match any registered planet, Orbit exits with a clear error listing configured planets.

All other commands (`destroy`, `attach`, `jump`, `list`) work from any directory — they look up orbits by name in state and do not require a planet directory.

---

## Branch Name Sanitization

Raw branch names are sanitized into a safe slug used in the default orbit name and worktree path:

1. Lowercase the branch name
2. Replace `/` with `-`
3. Replace any character that is not alphanumeric or `-` with `-`
4. Collapse consecutive `-` into one
5. Strip leading/trailing `-`
6. Truncate to 40 characters

Examples: `feature/auth-flow` → `feature-auth-flow`, `bugfix/auth-flow` → `bugfix-auth-flow`, `fix/FOO_bar` → `fix-foo-bar`, `main` → `main`.

Preserving the full branch path in the slug ensures that branches like `feature/auth-flow` and `bugfix/auth-flow` produce distinct slugs and never collide.

If the resulting default name (`{planet_slug}-{branch_slug}`) collides with an existing orbit, Orbit checks whether that orbit's tmux session is live:
- If live: `"An orbit named '{name}' already exists. Use --name to assign a unique name, or 'orbit destroy {name}' to tear it down first."`
- If stale: `"An orbit named '{name}' exists but its tmux session is no longer live (stale). Run 'orbit destroy {name}' to clean it up first."`

The `--name` flag is the escape hatch for live collisions.

---

## Key Behaviours

**Orbit launch (`orbit launch [branch] [--name <name>]`)**
- Requires CWD to be within a planet's directory — exits with a clear error listing configured planets if no match is found
- Requires a git repository in CWD — exits with a clear error if none is found
- Auto-detects branch from the CWD git repo if not provided
- Checks whether the branch exists on a remote using the following priority:
  1. If `origin` exists: check `origin` for the branch
  2. If no `origin` but other remotes exist: use the first alphabetically and print a notice naming the remote used
  3. If no remotes at all: create a new local branch
- If the branch exists on the chosen remote: checks out that branch in the worktree; otherwise creates a new local branch
- Sanitizes the branch name to a slug for use in the default orbit name
- Derives the orbit name: defaults to `{planet_slug}-{branch_slug}`; `--name` overrides this entirely
- Exits with a clear error if an orbit with that name already exists (see Branch Name Sanitization above)
- Creates `worktree_base` if it does not exist
- Creates a git worktree at `{worktree_base}/{orbit_name}`
- Appends `.orbit/` to the worktree's `.gitignore` if not already present (creates `.gitignore` if it does not exist)
- Collects all declared dev ports across all panes; for each, checks both ports claimed by active orbits in state and OS-level socket availability (a `socket.bind()` probe) — increments until a port passes both checks
- Writes a flat old→new port map to `.orbit/ports.json` in the worktree root
- Sets env vars on the tmux session via `tmux set-environment` **before** creating any panes, so all panes inherit them
- Creates the tmux session, splits panes per layout rules, sets each pane's working directory to the worktree root (or subdirectory if `directory` is set), and starts commands sequentially
- Panes with `command: null` are left as interactive shells; panes with no `directory` set default to the worktree root
- Records the orbit and its assigned ports in `~/.orbit/state.json`
- Prints the port assignment table
- If invoked from inside an existing tmux session: automatically switches the client to the new orbit's session via `tmux switch-client`; if invoked from outside tmux: prints attach instructions

**Orbit attach vs. switch**
- `orbit attach` is for entering an orbit from a plain terminal — it runs `tmux attach-session -t {name}`
- `orbit jump` is for jumping between orbits while already inside tmux — it runs `tmux switch-client -t {name}`, keeping you in the same terminal window
- Both use the same name-resolution logic (explicit name, single active, numbered prompt, or error)

**Orbit attach (`orbit attach [name]`)**
- If run from inside an existing tmux session, prints a warning: `"You are inside a tmux session. Use 'orbit jump' to jump between orbits without nesting sessions."` Then proceeds with the attach anyway (tmux supports nested sessions).

**Orbit jump (`orbit jump [name]`)**
- Resolves the target orbit using the standard name-resolution logic
- Supports prefix matching against the orbit name (session slug): `orbit jump auth` resolves unambiguously to `myapp-auth-flow` if it is the only match; shows the numbered prompt if ambiguous
- Calls `tmux switch-client -t {name}` to move the current tmux client to the target orbit's session instantly
- Exits with a clear error if not currently inside a tmux session (use `orbit attach` instead)

**Orbit destroy (`orbit destroy [name]`)**
- Checks whether the tmux session is live; if not, skips the kill step and proceeds with cleanup
- Kills the tmux session and all panes (if live)
- Releases claimed ports from state
- Removes the git worktree if it exists; skips removal with a notice if the worktree directory is missing (already cleaned up manually)
- Prompts for confirmation before removing the worktree if `git status --short` returns any output (includes modified, staged, and untracked files)
- Removes the orbit entry from state
- Stale orbits (tmux session no longer exists) are cleaned up through `orbit destroy` — their state entry and port claims are released as part of normal stop processing

**Port assignment**

Orbit owns port allocation. Each planet declares its standard dev ports in config — the ports the project normally uses locally. On `orbit launch`, Orbit checks each candidate port against two sources and increments until both pass:

1. Ports claimed by active orbits in `~/.orbit/state.json` (across all planets)
2. OS-level socket availability (a `socket.bind()` probe) — catches ports held by non-orbit processes

The result is written to `.orbit/ports.json` in the worktree root as a flat old→new map:

```json
{
  "5432": 5432,
  "6379": 6380,
  "3000": 3001
}
```

Ports that were free retain their original value.

On `orbit launch`, the assignment is also printed directly:

```
Started myapp-auth-flow

  Port  Assigned
  5432  5432
  6379  6380  (reassigned)
  3000  3001  (reassigned)

Port map written to .orbit/ports.json
```

- Ports are recorded in `~/.orbit/state.json` as assigned (not declared) values
- `orbit list` shows assigned ports per orbit
- Ports are released on `orbit destroy`

> **Note:** Orbit guarantees each orbit receives unique port assignments and records them in `ports.json`. The application processes running in each pane (e.g., `npm run dev`, `docker-compose up`) are responsible for reading `ports.json` and binding to the assigned ports — not their hardcoded defaults. Without this, Orbit prevents port-claim collisions between orbits, but the processes themselves may still attempt to bind to conflicting ports.

**Pane layouts**
- 1 pane: full screen
- 2 panes: side-by-side horizontal split
- 3 panes: large pane on the left, two stacked on the right
- 4 panes: full 2×2 grid
- 5+ panes: tmux `tiled` auto-layout

> Nexus integration (AI pair pane metadata and IPC) is planned for a future release.

---

## State Schema (`~/.orbit/state.json`)

Keyed by orbit name, which is also the tmux session name. Branch is stored as metadata.

```json
{
  "orbits": {
    "myapp-auth-flow": {
      "name": "myapp-auth-flow",
      "planet": "myapp",
      "branch": "feature/auth-flow",
      "worktree": "/Users/you/planets/myapp-auth-flow",
      "tmux_session": "myapp-auth-flow",
      "ports": { "3000": 3001, "5432": 5432, "6379": 6380 },
      "created_at": "2025-01-15T10:30:00Z"
    }
  }
}
```

---

## `orbit list` Output

```
ORBIT              PLANET    BRANCH              PORTS                STATUS
myapp-auth-flow    myapp     feature/auth-flow   3001,5432,6380        running
api-main           api       main                8000                  running
```

Ports shown are the **assigned** values, listed in pane declaration order. STATUS reflects whether the tmux session is confirmed live (`running` or `stale`). BRANCH shows the raw git branch name as stored in state.

---

## Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| CLI framework | Click |
| Package manager | uv |
| Session management | Direct tmux subprocess calls |
| Worktree management | Direct git subprocess calls |
| Config format | YAML (`~/.orbit/config.yaml`) |
| State storage | JSON (`~/.orbit/state.json`) |
| Validation | Pydantic models |

---

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
```

### Installation

```bash
# Dev install
uv sync

# Run without installing
uv run orbit

# Install as a global tool
uv tool install .
```
