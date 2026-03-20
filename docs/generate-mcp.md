# Generate MCP Server Workflow

Automatically generates [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) servers from a service's OpenAPI specification. Each OpenAPI tag becomes a namespaced MCP tool group, making API endpoints available as tools for AI agents.

## How It Works

```
API running on server
    → fetch /openapi.json
    → normalize tags (rename spaces, conflicts)
    → mcp-generator-3.x generates FastMCP server (per-tag modules)
    → patch stub API client with real httpx calls
    → deploy to /home/lab/openclaw/mcp-servers/{name}/
    → install dependencies
    → refresh auth token
    → register in mcporter
    → smoke test (list tools)
```

## Usage

Add to your service's deploy workflow:

```yaml
generate-mcp:
  needs: deploy
  uses: 922-Studio/workflows/.github/workflows/generate-mcp.yml@main
  with:
    service_name: 'my-service'
    api_port: '3000'
  secrets:
    AUTH_EMAIL: ${{ secrets.AUTH_EMAIL }}
    AUTH_PASSWORD: ${{ secrets.AUTH_PASSWORD }}
```

### With All Options

```yaml
generate-mcp:
  needs: deploy
  uses: 922-Studio/workflows/.github/workflows/generate-mcp.yml@main
  with:
    service_name: 'homeapi'
    api_port: '8080'
    openapi_path: '/openapi.json'
    tag_renames: '{"Activity Log":"activity-log","WorkLogs":"worklogs","Tasks":"tasks-mgmt"}'
    mcp_base_dir: '/home/lab/openclaw/mcp-servers'
    generator_dir: '/home/lab/tools/mcp-generator'
    mcporter_config: '/home/lab/openclaw/workspace/config/mcporter.json'
    auth_url: 'http://localhost:8100'
    health_timeout: 30
  secrets:
    AUTH_EMAIL: ${{ secrets.AUTH_EMAIL }}
    AUTH_PASSWORD: ${{ secrets.AUTH_PASSWORD }}
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `service_name` | string | yes | — | MCP server name (used for output dir and mcporter) |
| `api_port` | string | yes | — | Port the API listens on |
| `openapi_path` | string | no | `/openapi.json` | Path to OpenAPI spec endpoint |
| `tag_renames` | string | no | `{}` | JSON map of tag renames for Python-safe names |
| `mcp_base_dir` | string | no | `/home/lab/openclaw/mcp-servers` | Base directory for MCP output |
| `generator_dir` | string | no | `/home/lab/tools/mcp-generator` | Path to mcp-generator tool |
| `mcporter_config` | string | no | `/home/lab/openclaw/workspace/config/mcporter.json` | mcporter registration file |
| `auth_url` | string | no | `""` | Auth service URL (empty = skip auth) |
| `health_timeout` | number | no | `30` | Seconds to wait for API health |

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `AUTH_EMAIL` | no | Email for auth login (needed if `auth_url` is set) |
| `AUTH_PASSWORD` | no | Password for auth login (needed if `auth_url` is set) |

## Tag Renames

OpenAPI tags with spaces or conflicting names cause issues with Python module generation. Use `tag_renames` to normalize them:

```json
{
  "Activity Log": "activity-log",
  "WorkLogs": "worklogs",
  "Tasks": "tasks-mgmt"
}
```

Rules:
- Tags with **spaces** will break Python imports — always rename them
- Tags that **collide** after normalization need unique names (e.g. `Tasks` vs `tasks`)

## Server Prerequisites

The workflow runs on a self-hosted runner and requires:

1. **Python 3.12+** with `python3-venv` package
2. **mcp-generator-3.x** (auto-installed on first run)
3. **Support files** in `generator_dir`:
   - `api_client_httpx.py` — httpx-based API client (replaces generated stubs)
   - `patch_api_methods.py` — patches generated method stubs with real HTTP calls

### First-Time Setup

The generator tool and support files only need to be set up once per server:

```bash
# Clone generator
git clone https://github.com/quotentiroler/mcp-generator-3.x.git /home/lab/tools/mcp-generator
cd /home/lab/tools/mcp-generator
python3 -m venv .venv && source .venv/bin/activate && pip install -e .

# Support files (api_client_httpx.py and patch_api_methods.py)
# These are already in place if you've run the workflow before.
# If not, they need to be created manually — see the Planner repo
# scripts/patch_api_methods.py for reference.
```

## Output Structure

Each generated MCP server lives in `{mcp_base_dir}/{service_name}/`:

```
/home/lab/openclaw/mcp-servers/homeapi/
├── .venv/                          # Python venv (persists across rebuilds)
├── .api-token                      # Auth token (auto-refreshed)
├── run.sh                          # mcporter wrapper script
├── homeapi_mcp_generated.py        # FastMCP entry point
├── servers/                        # Per-tag tool modules
│   ├── debts_server.py
│   ├── gmail_server.py
│   ├── quotes_server.py
│   └── ...
├── generated_openapi/              # Patched API client
│   └── openapi_client/
├── middleware/                      # Auth middleware
│   └── authentication.py
└── fastmcp.json                    # FastMCP config
```

## Adding to a New Microservice

1. Ensure your service has an OpenAPI/Swagger spec endpoint
2. Add the workflow job to your deploy pipeline (see Usage above)
3. Add `AUTH_EMAIL` and `AUTH_PASSWORD` to your GitHub repo secrets (if auth is needed)
4. Push — the workflow auto-installs the generator, generates, and registers

No manual server setup needed for new services. The workflow handles everything.

## Known Limitations

- **Google OAuth endpoints** (Calendar, Gmail) won't work through MCP since they need separate OAuth flows
- **Non-JSON responses** (e.g. Prometheus `/metrics`) will error — this is expected
- **Token expiry** — tokens are refreshed on each deploy. For long-running sessions, manually refresh or add a cron job
- **mcp-generator-3.x generates stub API clients** — the `patch_api_methods.py` and `api_client_httpx.py` scripts fix this by injecting real httpx calls
