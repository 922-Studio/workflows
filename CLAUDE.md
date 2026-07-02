# Project: Workflows (922-Studio Reusable Workflows)

## Overview
- **Type**: infra
- **Path**: /Users/gregor/dev/922/workflows
- **Status**: active
- **Description**: Reusable GitHub Actions workflow library for the 922-Studio org. Single source of truth for CI/CD — all repos call these via `workflow_call`. Covers AI-powered semantic versioning, Docker deploy, smoke tests, Python/frontend test automation, and unified email + Discord notifications.

## Tech Stack
- **Language(s)**: YAML (GitHub Actions), Python 3.13, Bash
- **Framework(s)**: GitHub Actions `workflow_call` pattern
- **Infrastructure**: Self-hosted runners on astro-antares cluster
- **CI/CD**: None for this repo — it IS the CI/CD

## Key Files to Read

| File | Purpose | When to read |
|------|---------|--------------|
| `README.md` | Overview, available workflows, usage | First time |
| `.github/workflows/versioning.yml` | AI-powered semver via Gemini | Touching versioning |
| `.github/workflows/deploy-docker.yml` | Docker service deployment | Touching deployment |
| `.github/workflows/smoke-test.yml` | Pre-deployment smoke testing | Touching test gating |
| `.github/workflows/send-notification.yml` | Unified email + Discord | Touching notifications |
| `.github/scripts/determine_version.py` | Conventional commit + Gemini logic | Touching version logic |
| `docs/versioning.md` | Versioning workflow deep-dive | Deep understanding |

## Best Practices
- All workflows use `on: workflow_call` with explicit `inputs`, `secrets`, `outputs`.
- Consumers call via `uses: 922-Studio/workflows/.github/workflows/{name}.yml@main` + `secrets: inherit`.
- Python scripts: stdlib only (exception: `google-generativeai`). HTTP=`urllib`, email=`smtplib`, XML=`xml.etree`.
- Type hints throughout Python code.
- Step names use emoji prefix + description for scannability.
- Error handling: critical→`exit 1`, non-fatal→log+continue, API failure→fallback (Gemini→PATCH, Discord→default channel).
- Notification colours: success=`#28a745`, failure=`#dc3545`, cancelled=`#6c757d`.
- `[ci skip]` in commit message skips versioning.

### Naming

| What | Pattern |
|------|---------|
| Workflows | `kebab-case.yml` |
| Scripts | `snake_case.py` |
| Functions | `snake_case` |
| Constants/env | `UPPER_SNAKE_CASE` |
| Docs | `kebab-case.md` |

### Caller workflow `name:` convention
`{RepoName} {Action} [{Subject}]` — e.g. `HomeUI Deploy`, `HomeAPI Deploy Documentation`. Full table: `HomeStructure/docs/actions/workflow-naming.md`.

### Versioning
Conventional commits: `fix:`→PATCH, `feat:`→MINOR, `feat!:`→MAJOR; highest wins. Optional Gemini 2.5 Flash mode analyses the diff. Version stored in `version.txt`.

### E2E dispatch pattern
Caller repo's `e2e.yml` is `workflow_dispatch`-only and calls `frontend-e2e.yml@main`. `deploy.yml` fires `gh workflow run e2e.yml` after unit tests, then continues to smoke+deploy without waiting. Affected: HomeUI, Portfolio.

## Testing Strategy
- **Unit tests**: `.github/tests/` — pytest. Run: `pytest .github/tests/`.
- **Coverage**: conventional commit detection, CLI routing, edge cases for versioning script.
- **Consumer tests**: pytest / Vitest invoked via `python-tests.yml` / `frontend-tests.yml`; Allure reporting with configurable coverage threshold.

## Documentation
- **Where**: `README.md`, `docs/` (versioning, deploy-docker, send-email, smoke-test, generate-mcp), `.planning/codebase/`.
- **Update rule**: Update docs whenever a workflow's `inputs`/`outputs`/`secrets` contract changes.

## Pipeline & Deployment
- **CI trigger**: N/A — this repo is consumed, not deployed.
- **Consumers**: `uses: 922-Studio/workflows/.github/workflows/{name}.yml@main` + `secrets: inherit`.
- **Typical chain**: versioning → test → smoke-test → deploy → notify.
- **Monitor after push**: verify downstream consumer pipelines still pass (HomeUI, HomeAPI, Portfolio are good canaries).

## Dependencies on Other Projects
- No upstream deps. Every other 922-Studio project depends on this repo for CI/CD — breaking changes ripple ecosystem-wide; bump cautiously and pin via tag/SHA when needed.

## Notes
- 13 reusable workflows: cancel-previous-runs, versioning, python-lint, python-tests, smoke-test, deploy-docker, frontend-tests, frontend-e2e, docker-build, generate-mcp, create-issue, send-notification.
- Defaults: Node 20.x, Python 3.13, Allure at `http://astro-antares:5050`.
- All workflows require self-hosted runners.

## New Workflow Checklist
1. `.github/workflows/{name}.yml` — `on: workflow_call` with explicit inputs/secrets/outputs.
2. Helper in `.github/scripts/` (stdlib Python) if needed.
3. Docs in `docs/{name}.md`.
4. Tests in `.github/tests/test_{name}.py`.
