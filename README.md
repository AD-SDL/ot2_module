# ot2_module

A MADSci node module for integrating Opentrons liquid handlers (OT-2 and Flex) into an automated/autonomous laboratory.

## Configuration

All configuration is done via environment variables (prefixed `NODE_`), a `settings.yaml` file, or a `.env` file. See [docs/Configuration.md](docs/Configuration.md) for the full reference and `.env.example` for a commented template.

The most important settings to configure:

| Variable | Default | Purpose |
|---|---|---|
| `NODE_OT2_IP` | _(required)_ | IP address of the Opentrons robot |
| `NODE_URL` | `http://127.0.0.1:2000/` | URL the node binds to and advertises |
| `NODE_NODE_NAME` | _(class name)_ | Human-readable name registered with MADSci |
| `NODE_NODE_ID` | _(auto-generated)_ | Stable node identifier (ULID); set to persist identity across restarts |

Configuration is loaded in priority order: environment variables > `.env` file > `settings.yaml`. A minimal `settings.yaml` might look like:

```yaml
node_name: ot2_beta
node_description: OT-2 Beta liquid handler in the RPL workcell
node_id: 01JPNMZF3SPK48EWA1VXMVYHWV
ot2_ip: 192.168.1.100
node_url: "http://127.0.0.1:2000/"
```

## Getting Started

### Option 1 — Devbox (recommended)

[Devbox](https://www.jetify.com/docs/devbox/) provides a reproducible shell with Python 3.12, pdm, uv, ruff, pre-commit, and just pre-installed. [direnv](https://direnv.net/) integration via `.envrc` activates the environment automatically when you `cd` into the directory.

```bash
devbox shell        # enter the reproducible environment (or let direnv handle it)
just init           # install dependencies + pre-commit hooks
```

### Option 2 — PDM + uv

```bash
pdm install -G:all  # install all dependencies including dev extras
```

PDM automatically uses uv as the resolver/installer when `PDM_USE_UV=True` is set (set in `devbox.json`).

### Option 3 — pip / uv (minimal)

```bash
# Standard pip
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install .

# Or with uv (faster)
uv venv
source .venv/bin/activate
uv pip install .
```

## Running the Node

```bash
python -m ot2_rest_node
```

The node reads all settings from `settings.yaml`, environment variables, or `.env`. The Opentrons robot HTTP API must be reachable at the configured `NODE_OT2_IP`.

## Development

### Tooling overview

| Tool | Purpose |
|---|---|
| [devbox](https://www.jetify.com/docs/devbox/) | Reproducible dev shell (Python 3.12, pdm, uv, ruff, just, pre-commit) |
| [pdm](https://pdm-project.org/) | Dependency management and virtual environment |
| [uv](https://docs.astral.sh/uv/) | Fast pip-compatible installer (used by pdm via `PDM_USE_UV`) |
| [just](https://just.systems/) | Task runner (`just --list` to see all commands) |
| [ruff](https://docs.astral.sh/ruff/) | Linter and formatter |
| [pre-commit](https://pre-commit.com/) | Git hooks for linting, formatting, and config generation |

### Common commands

```bash
just checks   # ruff lint + format + config checks (auto-fixes then re-checks)
just test     # pytest (skip hardware tests with: pytest -m "not hardware")
just dcb      # docker compose build
```

Pre-commit also runs [pydantic-settings-export](https://github.com/jag-k/pydantic-settings-export) to keep `docs/Configuration.md` and `.env.example` up to date whenever `src/ot2_rest_node.py` changes.

## Docker

A pre-built image is available at `ghcr.io/ad-sdl/ot2_module`. To run with Docker Compose:

```bash
# Copy and edit the example settings and env files
cp .env.example .env
# Edit settings.yaml with your robot's IP and node identity

docker compose up
```

The container uses `network_mode: host` so it can reach the Opentrons robot on the local network. The `settings.yaml` and `.madsci/` directory are bind-mounted from the project root.

Set `USER_ID` and `GROUP_ID` to match your host user to avoid file permission issues:

```bash
USER_ID=$(id -u) GROUP_ID=$(id -g) docker compose up
```

## SSH Access to the OT-2

> SSH access is **not required** for the HTTP driver used by this module.

If you need SSH access for debugging, see the Opentrons documentation:
- [Setting up SSH access to your OT-2](https://support.opentrons.com/en/articles/3203681-setting-up-ssh-access-to-your-ot-2)
- [Connecting to your OT-2 with SSH](https://support.opentrons.com/en/articles/3287453-connecting-to-your-ot-2-with-ssh)
