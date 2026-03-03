# Workflows

## Git Commits
- Do NOT add `Co-Authored-By` trailers to any git commit messages

Reusable GitHub Actions workflow library for 922-Studio org. All workflows use `workflow_call`.

## Layout

`.github/workflows/` — reusable YAML. `.github/scripts/` — Python helpers. `.github/tests/` — script tests. `docs/` — per-workflow docs.

## Naming

| What | Pattern |
|------|---------|
| Workflows | `kebab-case.yml` |
| Scripts | `snake_case.py` |
| Functions | `snake_case` |
| Constants/env | `UPPER_SNAKE_CASE` |
| Step names | emoji + description |
| Docs | `kebab-case.md` |

## Patterns

**Workflow contract:**
```yaml
on:
  workflow_call:
    inputs: { param: { type: string, required: true } }
    secrets: { NAME: { required: true } }
    outputs: { result: { value: "${{ jobs.j.outputs.v }}" } }
```
Called via: `uses: 922-Studio/workflows/.github/workflows/{name}.yml@main` + `secrets: inherit`.

**Scripts:** Python stdlib only (exception: `google-generativeai` for versioning). HTTP=`urllib`, email=`smtplib`, XML=`xml.etree`. Type hints throughout.

**Errors:** critical→exit 1, non-fatal→log+continue, fallbacks (version defaults to PATCH, Discord to default channel).

**Versioning:** conventional commits (`fix:`→PATCH, `feat:`→MINOR, `feat!:`→MAJOR), highest wins, optional Gemini AI mode. Version in `version.txt`.

**Notifications:** success=`#28a745` failure=`#dc3545` cancelled=`#6c757d`.

## Testing

pytest for `.github/tests/`. Consuming repos use pytest/Vitest via these workflows. Allure reporting, configurable coverage threshold.

```bash
pytest .github/tests/
```

## New Workflow Checklist

1. `.github/workflows/{name}.yml` — `on: workflow_call`, explicit inputs/secrets/outputs
2. Helper in `.github/scripts/` if needed (stdlib Python)
3. Docs in `docs/{name}.md`
4. Tests in `.github/tests/test_{name}.py`
