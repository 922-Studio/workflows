# Reusable GitHub Actions Workflows

This repository contains reusable GitHub Actions workflows for automating common development and deployment tasks.

## Available Workflows

### 1. AI-Powered Versioning
Automates semantic versioning using Google's Gemini API. It analyzes commit messages to determine the next version number, updates a `version.txt` file, and creates a new version tag.

**Documentation**: [docs/versioning.md](docs/versioning.md)

### 2. Docker Service Deployment
Automates deployment of Docker services to a self-hosted runner with comprehensive logging and error handling.

**Documentation**: [docs/deploy-docker.md](docs/deploy-docker.md)

### 3. Send Email Notification
Sends email notifications via Gmail SMTP with support for both default workflow status templates and custom HTML email bodies. Supports multiple recipients and robust error handling.

**Documentation**: [docs/send-email.md](docs/send-email.md)

### 4. Send Notification (Email + Discord)
Sends notifications via email and/or Discord from a single reusable workflow. Supports toggling each channel independently (email only, Discord only, or both by default) and shares common workflow metadata between the email template and Discord embed.

### 5. Smoke Test (Docker Compose)
Comprehensive post-deployment smoke test for Docker Compose stacks. Checks all containers are running, Docker healthchecks pass, database migrations succeeded, and HTTP health endpoints respond. Outputs per-service diagnostics on failure.

**Documentation**: [docs/smoke-test.md](docs/smoke-test.md)

### 6. Generate MCP Server
Automatically generates MCP (Model Context Protocol) servers from a service's OpenAPI specification. Each OpenAPI tag becomes a namespaced MCP tool group, making API endpoints available as tools for AI agents. Handles generator installation, spec normalization, API client patching, deployment, auth token refresh, and mcporter registration.

**Documentation**: [docs/generate-mcp.md](docs/generate-mcp.md)

### 7. PR Preview Environment
Manages Docker-based PR preview environments on a self-hosted runner. Spins up an isolated container stack per PR branch on open/sync (with a Traefik-routed public subdomain or Tailscale IP fallback) and tears it down on close. Posts and updates a PR comment with the live preview URL throughout the PR lifecycle.

**Documentation**: [docs/pr-demo.md](docs/pr-demo.md)

### 8. Frontend Tests
Runs a Node.js frontend test suite (Vitest) on a self-hosted runner with local disk caching for `node_modules`, optional build verification, Allure result uploads, and optional Prometheus Pushgateway coverage reporting. Supports npm and pnpm (via corepack), configurable working directories, and failure notifications via email or Discord.

### 9. Cancel Previous Runs
Cancels any in-progress or queued runs of the same workflow on the same branch when a new run starts, preventing redundant CI work on rapid pushes.

## Usage

To use this workflow in your own repository, create a new workflow file (e.g., `.github/workflows/release.yml`) with the following content:

```yaml
name: Create New Version

on:
  push:
    branches:
      - main

jobs:
  version:
    uses: <your-username>/<this-repo-name>/.github/workflows/versioning.yml@main
    with:
      gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
      # Optional: Specify a self-hosted runner
      # runs-on: self-hosted
```

### Prerequisites

1.  **Gemini API Key:** You must have a Gemini API key. You can get one from [Google AI Studio](https://aistudio.google.com/app/apikey).

2.  **Add API Key as a Secret:** In your repository, go to `Settings > Secrets and variables > Actions` and add a new repository secret named `GEMINI_API_KEY` with your API key as the value.

3.  **Grant Permissions:** The workflow needs permission to push changes back to your repository. Go to `Settings > Actions > General` and under "Workflow permissions," select "Read and write permissions."

## How it Works

When triggered, the workflow will:

1.  Check out your repository's code.
2.  Find the most recent version tag.
3.  Gather all commit messages since that tag.
4.  Send the commit messages to the Gemini API to determine if the version bump should be `MAJOR`, `MINOR`, or `PATCH`.
5.  Update the `version.txt` file in your repository.
6.  Commit and push the updated `version.txt`.
7.  Create and push a new version tag.

For more detailed information, please see the [documentation](docs/versioning.md).
