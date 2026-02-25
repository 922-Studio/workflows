# Smoke Test (Docker Compose)

Comprehensive post-deployment smoke test for Docker Compose stacks. Verifies every container is running, passes Docker healthchecks, database migrations succeeded, and HTTP health endpoints respond.

## Usage

```yaml
smoke-test:
  needs: deploy
  uses: 922-Studio/workflows/.github/workflows/smoke-test.yml@main
  with:
    repository_path: '/home/lab/MyProject'
    expected_services: 'db,api,redis,worker'
    healthcheck_urls: '{"api":"http://localhost:8080/health"}'
    migration_service: 'api'
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `repository_path` | yes | — | Absolute path to repo on self-hosted runner |
| `docker_compose_file` | no | `docker-compose.yaml` | Compose file relative to repo root |
| `working_directory` | no | repo root | Subdirectory for compose commands |
| `expected_services` | no | auto-discover | Comma-separated service names (e.g. `db,api,redis`) |
| `healthcheck_urls` | no | `{}` | JSON map of service→URL for HTTP checks |
| `migration_service` | no | — | Service that runs DB migrations on startup |
| `migration_success_pattern` | no | `Running upgrade` | Grep pattern for migration success |
| `migration_failure_patterns` | no | `alembic.util.exc\|FAILED\|...` | Grep -E pattern for migration failure |
| `max_retries` | no | `30` | Max healthcheck attempts |
| `retry_delay_seconds` | no | `5` | Delay between attempts |

## Outputs

| Output | Description |
|--------|-------------|
| `result` | `passed` or `failed` |

## What it checks

1. **Container status** — Every expected service has a running container (detects crash loops, startup failures)
2. **Docker healthchecks** — Services with `healthcheck:` in compose file reach `healthy` state (detects DB connection failures, internal errors)
3. **Database migrations** — Scans migration service logs for success/failure patterns (detects Alembic errors, schema conflicts)
4. **HTTP endpoints** — Curls health URLs and expects 2xx/3xx response (detects app-level failures, routing issues)

## Failure diagnostics

On failure, the workflow automatically dumps:
- Per-service container logs (last 80 lines each)
- Final container status table
- Docker system disk usage

## Examples

### API with database (HomeAPI-style)

```yaml
smoke-test:
  needs: deploy
  uses: 922-Studio/workflows/.github/workflows/smoke-test.yml@main
  with:
    repository_path: '/home/lab/HomeAPI'
    expected_services: 'db,api,redis,worker,beat'
    healthcheck_urls: '{"api":"http://localhost:8080/health"}'
    migration_service: 'api'
    migration_success_pattern: 'Running upgrade'
```

### Frontend-only service

```yaml
smoke-test:
  needs: deploy
  uses: 922-Studio/workflows/.github/workflows/smoke-test.yml@main
  with:
    repository_path: '/home/lab/MyFrontend'
    expected_services: 'web'
    healthcheck_urls: '{"web":"http://localhost:3000"}'
```

### Auto-discover all services

```yaml
smoke-test:
  needs: deploy
  uses: 922-Studio/workflows/.github/workflows/smoke-test.yml@main
  with:
    repository_path: '/home/lab/MyProject'
    healthcheck_urls: '{"api":"http://localhost:8080/health","web":"http://localhost:3000"}'
```

## vs frontend-smoke.yml

`frontend-smoke.yml` starts a single service and polls one URL. `smoke-test.yml` checks an entire running stack — all containers, Docker health status, migrations, and multiple HTTP endpoints. Use `smoke-test.yml` for post-deployment validation of multi-service stacks.

## Prerequisites

- Self-hosted runner with Docker and Docker Compose
- Stack must already be running (this workflow does **not** start containers — run after `deploy-docker.yml`)
