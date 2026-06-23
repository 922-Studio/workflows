# PR Preview Environment

This reusable GitHub Actions workflow manages Docker-based PR preview environments on a self-hosted runner. When a pull request is opened or updated, it spins up an isolated container stack for that branch and posts the preview URL as a PR comment. When the PR is closed, the environment is torn down and all resources are cleaned up.

## Features

- **Git Worktrees**: Each PR gets its own isolated git worktree so previews don't interfere with the main checkout or each other
- **Traefik Routing**: When `preview_domain` is set, environments are routed via Traefik with public subdomains (e.g. `drafter-pr-42.922-studio.com`)
- **Public Subdomain Support**: Optionally expose previews publicly via a domain; falls back to Tailscale IP when no domain is set
- **Port Wrapping**: Preview port is computed as `PORT_BASE + (PR_NUMBER % PORT_RANGE)`, keeping ports in a bounded range across all PRs
- **Port Availability Checking**: Detects both port collisions from wrapping and ports bound by other processes before starting
- **Healthchecks**: Polls the configured healthcheck path until the container responds (or times out), then reports status
- **PR Comment Updates**: Posts the preview URL as a PR comment on deploy; updates the same comment on teardown using `--edit-last` to avoid spam
- **Capacity Limits**: Enforces a configurable maximum number of concurrent previews; rejects new ones when the runner is at capacity

## Usage

Create a workflow file (e.g., `.github/workflows/pr-demo.yml`) in your repository:

```yaml
name: Drafter PR Preview

permissions:
  contents: read
  pull-requests: write

on:
  pull_request:
    types: [opened, synchronize, closed]

jobs:
  deploy-preview:
    name: Deploy PR preview
    if: github.event.action == 'opened' || github.event.action == 'synchronize'
    uses: 922-Studio/workflows/.github/workflows/pr-demo.yml@main
    with:
      repository_path: '/home/lab/Drafter'
      project_name: 'drafter'
      port_base: '9100'
      healthcheck_path: '/api/health'
      preview_domain: '922-studio.com'
      action: 'start'
    secrets:
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}

  cleanup-preview:
    name: Cleanup PR preview
    if: github.event.action == 'closed'
    uses: 922-Studio/workflows/.github/workflows/pr-demo.yml@main
    with:
      repository_path: '/home/lab/Drafter'
      project_name: 'drafter'
      port_base: '9100'
      action: 'stop'
    secrets:
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}
```

Note: The caller must pass `action: 'start'` or `action: 'stop'` explicitly. The `github.event.action` value is not reliably forwarded inside reusable workflows.

## Inputs

### `repository_path` (required)
- **Type**: `string`
- **Description**: Absolute path to the repository on the self-hosted runner
- **Example**: `/home/lab/Drafter`

### `project_name` (required)
- **Type**: `string`
- **Description**: Short identifier for the project. Used in container names, compose project names, and state files
- **Example**: `drafter`

### `action` (required)
- **Type**: `string`
- **Description**: PR action to perform: `start` (for opened/synchronize events) or `stop` (for closed events)
- **Values**: `start` | `stop`

### `port_base` (optional)
- **Type**: `string`
- **Default**: `9100`
- **Description**: Base port number. Each PR is assigned a port computed as `port_base + (PR_NUMBER % port_range)`

### `port_range` (optional)
- **Type**: `string`
- **Default**: `100`
- **Description**: Port range before wrapping. With the default of `100`, PR #100 reuses the same port as PR #0

### `compose_file` (optional)
- **Type**: `string`
- **Default**: `docker-compose.yaml`
- **Description**: Docker Compose file to use, relative to the repository root

### `healthcheck_path` (optional)
- **Type**: `string`
- **Default**: `/api/health`
- **Description**: HTTP path used to verify that the preview container is up and healthy

### `healthcheck_timeout` (optional)
- **Type**: `string`
- **Default**: `60`
- **Description**: Seconds to wait for the healthcheck to pass before reporting the preview as started

### `max_demos` (optional)
- **Type**: `string`
- **Default**: `5`
- **Description**: Maximum number of concurrent preview environments allowed on the runner

### `preview_domain` (optional)
- **Type**: `string`
- **Default**: `""` (empty)
- **Description**: Domain for public preview URLs. When set, generates `{project_name}-pr-{N}.{preview_domain}` and enables Traefik routing. When empty, falls back to Tailscale IP
- **Example**: `922-studio.com`

### `tailscale_ip` (optional)
- **Type**: `string`
- **Default**: `100.112.171.16`
- **Description**: Tailscale IP of the self-hosted runner. Used only when `preview_domain` is empty to construct the fallback URL

## Secrets

### `PAT_GITHUB` (required)
- **Description**: Personal Access Token used to check out the workflows repository (to fetch `pr-demo.sh`) and to post PR comments via the GitHub CLI
- **Required scopes**: `repo` (full control of private repositories)

## How It Works

### Deploy (PR opened or updated)

1. **Log inputs**: Displays all parameters for debugging
2. **Checkout workflow scripts**: Clones the `922-Studio/workflows` repository to access `pr-demo.sh`
3. **Start preview**: Calls `pr-demo.sh start <pr-number> <branch>` with all configuration passed as environment variables
4. **Extract preview URL**: Parses the `STARTED pr=N url=...` line from script output; falls back to computing the URL from inputs if parsing fails
5. **Post PR comment**: Creates or updates a PR comment with the preview URL, branch, and timestamp using `gh pr comment --edit-last`
6. **Show logs on failure**: On error, dumps Docker Compose logs and system resource info

### Teardown (PR closed)

1. **Log cleanup start**: Displays PR number and close reason (merged or closed)
2. **Checkout workflow scripts**: Same as above
3. **Stop preview**: Calls `pr-demo.sh stop <pr-number>` to tear down containers, remove the git worktree, and delete state files
4. **Update PR comment**: Updates the existing comment to show the preview is offline

## Configuration

All configuration is passed to `pr-demo.sh` via environment variables:

| Variable | Input | Default |
|---|---|---|
| `PROJECT_NAME` | `project_name` | — |
| `REPO_PATH` | `repository_path` | — |
| `PORT_BASE` | `port_base` | `9100` |
| `PORT_RANGE` | `port_range` | `100` |
| `MAX_DEMOS` | `max_demos` | `5` |
| `COMPOSE_FILE` | `compose_file` | `docker-compose.yaml` |
| `PREVIEW_DOMAIN` | `preview_domain` | `""` |
| `TAILSCALE_IP` | `tailscale_ip` | `100.112.171.16` |
| `HEALTHCHECK_PATH` | `healthcheck_path` | `/api/health` |
| `HEALTHCHECK_TIMEOUT` | `healthcheck_timeout` | `60` |

### Public Access via `PREVIEW_DOMAIN`

When `preview_domain` is set, the script:
- Generates a subdomain URL: `https://{project_name}-pr-{N}.{preview_domain}`
- Sets `TRAEFIK_ENABLE=true` and `TRAEFIK_HOST={project_name}-pr-{N}.{preview_domain}` in the preview `.env`
- Verifies health by hitting `http://localhost{healthcheck_path}` with the appropriate `Host` header so Traefik can route the request

When `preview_domain` is empty:
- Falls back to `http://{tailscale_ip}:{port}`
- Sets `TRAEFIK_ENABLE=false` in the preview `.env`
- Verifies health by hitting `http://localhost:{port}{healthcheck_path}` directly

### Port Wrapping

Each PR is assigned a port using the formula:

```
port = PORT_BASE + (PR_NUMBER % PORT_RANGE)
```

With defaults (`PORT_BASE=9100`, `PORT_RANGE=100`):
- PR #1 → port 9101
- PR #42 → port 9142
- PR #100 → port 9100 (wraps back to base)
- PR #142 → port 9142 (same port as PR #42)

The script detects port collisions from wrapping: if a port is already in use by another running PR, the new start is rejected with `PORT_CONFLICT`. Stale state files without a running container are cleaned up automatically.

## State Management

Preview state is tracked in JSON files on the runner:
- State directory: `/tmp/{project_name}-pr-state/`
- State file per PR: `/tmp/{project_name}-pr-state/pr-{N}.json`
- Git worktrees: `/tmp/{project_name}-pr/pr-{N}/`

Each state file records the PR number, branch, port, compose project name, URL, and start time.

## Prerequisites

1. **Self-hosted runner**: A GitHub Actions runner must be installed and running on the server
   ```bash
   sudo ./svc.sh start
   ```

2. **Docker and Docker Compose**: Must be installed on the runner
   ```bash
   docker --version
   docker compose version
   ```

3. **Git**: Must be installed and the repository must already be cloned at `repository_path`
   ```bash
   git -C /home/lab/Drafter status
   ```

4. **Repository cloned on server**: The repository must exist at the path specified in `repository_path`. The workflow creates worktrees from this clone; it does not perform a fresh checkout

5. **GitHub Personal Access Token**: Required to fetch the workflows repo and post PR comments
   - Create a PAT at [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
   - Required scopes: `repo`
   - Add as repository secret named `PAT_GITHUB`

6. **Traefik** (if using `preview_domain`): Traefik must be running on the server and configured to pick up Docker labels, so it can route traffic to the preview containers by subdomain
