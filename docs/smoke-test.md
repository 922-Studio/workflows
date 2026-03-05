# Smoke Test (Docker Compose)

Pre-deployment smoke test that builds and runs an **isolated** container stack alongside production. Verifies images build, containers start, Docker healthchecks pass, database migrations succeed, and HTTP health endpoints respond — all without touching the running production stack.

## How it works

1. **Pull code** — Fetches latest changes (optional, toggleable via `pull_code`)
2. **Generate isolated compose** — Python script strips `container_name`, remaps ports to random, prefixes volumes so nothing clashes with production
3. **Build images** — `docker compose build` validates Dockerfiles and dependencies
4. **Start isolated stack** — Containers run under project name `smoke-{run_id}` with random ports
5. **Run checks** — Container status, Docker healthchecks, migration logs, HTTP endpoints
6. **Tear down** — Removes all smoke containers, volumes, and temp files (always, even on failure)

## Usage

```yaml
smoke-test:
  needs: tests
  uses: 922-Studio/workflows/.github/workflows/smoke-test.yml@main
  with:
    repository_path: '/home/lab/MyProject'
    expected_services: 'db,api,redis,worker'
    healthcheck_endpoints: '{"api":"8080:/health"}'
    migration_service: 'api'
    pull_code: true
    env_file_source: '/home/lab/MyProject/.env'
  secrets:
    PAT_GITHUB: ${{ secrets.PAT_GITHUB }}

deploy:
  needs: smoke-test
  uses: 922-Studio/workflows/.github/workflows/deploy-docker.yml@main
  with:
    repository_path: '/home/lab/MyProject'
    pull_code: false  # smoke-test already pulled
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `repository_path` | yes | — | Absolute path to repo on self-hosted runner |
| `docker_compose_file` | no | `docker-compose.yaml` | Compose file relative to repo root |
| `working_directory` | no | repo root | Subdirectory for compose commands |
| `expected_services` | no | auto-discover | Comma-separated service names (e.g. `db,api,redis`) |
| `healthcheck_endpoints` | no | `{}` | JSON map of `service → container_port:path` (e.g. `{"api":"8080:/health"}`) |
| `migration_service` | no | — | Service that runs DB migrations on startup |
| `migration_success_pattern` | no | `Running upgrade` | Grep pattern for migration success in logs |
| `migration_failure_patterns` | no | `alembic.util.exc\|FAILED\|...` | Grep -E pattern for migration failure |
| `max_retries` | no | `30` | Max healthcheck attempts |
| `retry_delay_seconds` | no | `5` | Delay between attempts |
| `pull_code` | no | `true` | Whether to git pull before building |
| `env_file_source` | no | — | Path to `.env` file to copy for smoke containers |

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `PAT_GITHUB` | no | GitHub PAT for pulling private repos |

## Outputs

| Output | Description |
|--------|-------------|
| `result` | `passed` or `failed` |

## What it checks

1. **Image build** — All Dockerfiles compile, dependencies install correctly
2. **Container startup** — Every expected service has a running container (detects crash loops, OOM kills)
3. **Docker healthchecks** — Services with `healthcheck:` reach `healthy` state
4. **Database migrations** — Scans migration service logs for Alembic success/failure patterns
5. **HTTP endpoints** — Resolves random host ports via `docker compose port`, curls health paths

## Isolation

The smoke stack is fully isolated from production:

- **Project name**: `smoke-{github.run_id}` — different Docker network and container names
- **No `container_name`**: Stripped so Docker Compose uses project-prefixed names
- **Random ports**: Host ports set to `0` (OS assigns random available ports)
- **Prefixed volumes**: Named volumes get `smoke-{id}_` prefix, never touching production data
- **No restart policy**: Smoke containers don't restart on failure (cleaner diagnostics)
- **Full cleanup**: `docker compose down -v --remove-orphans --rmi local` removes containers, volumes, and locally built images

## Failure diagnostics

On failure, the workflow automatically dumps:
- Per-service container logs (last 80 lines each)
- Final container status table

## Examples

### API with database (HomeAPI-style)

```yaml
smoke-test:
  needs: tests
  uses: 922-Studio/workflows/.github/workflows/smoke-test.yml@main
  with:
    repository_path: '/home/lab/HomeAPI'
    expected_services: 'db,api,redis,worker,beat'
    healthcheck_endpoints: '{"api":"8080:/health"}'
    migration_service: 'api'
    env_file_source: '/home/lab/HomeAPI/.env'
  secrets:
    PAT_GITHUB: ${{ secrets.PAT_GITHUB }}
```

### Frontend-only service

```yaml
smoke-test:
  needs: tests
  uses: 922-Studio/workflows/.github/workflows/smoke-test.yml@main
  with:
    repository_path: '/home/lab/MyFrontend'
    expected_services: 'web'
    healthcheck_endpoints: '{"web":"3000:/"}'
```

### Auto-discover all services

```yaml
smoke-test:
  uses: 922-Studio/workflows/.github/workflows/smoke-test.yml@main
  with:
    repository_path: '/home/lab/MyProject'
    healthcheck_endpoints: '{"api":"8080:/health","web":"3000:/"}'
```

## Prerequisites

- Self-hosted runner with Docker, Docker Compose, Python 3, and `curl`
- `.env` file accessible on the runner (if services require env vars)
