# Docker Deployment Workflow

This reusable GitHub Actions workflow automates the deployment of Docker services to a self-hosted runner. It pulls the latest code, builds Docker images, and restarts services with comprehensive logging for debugging.

## Features

- **Automated Git Pull**: Fetches and resets to the latest commit from the repository
- **Flexible Deployment**: Deploy all services or a specific service
- **Comprehensive Logging**: Every step includes detailed logs with emojis for easy scanning
- **Error Handling**: Graceful failure handling with full log dumps on error
- **Container Verification**: Checks container status after deployment
- **Image Cleanup**: Removes dangling Docker images to save space

## Usage

To use this workflow in your repository, create a workflow file (e.g., `.github/workflows/deploy.yml`):

```yaml
name: Deploy to Server

on:
  push:
    branches:
      - main
    paths:
      - 'src/**'
      - 'docker-compose.yml'

jobs:
  deploy:
    uses: 922-Studio/workflows/.github/workflows/deploy-docker.yml@main
    with:
      repository_path: /home/lab/your-repo
      docker_compose_file: docker-compose.yml
      service_name: web  # Optional: omit to deploy all services
      working_directory: ''  # Optional: subdirectory for docker-compose
    secrets:
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}  # Optional: for private repos
```

## Inputs

### `repository_path` (required)
- **Type**: `string`
- **Description**: Absolute path to the repository on the self-hosted runner
- **Example**: `/home/lab/HomeStructure`

### `docker_compose_file` (required)
- **Type**: `string`
- **Description**: Path to the docker-compose file relative to the repository root
- **Example**: `docker-compose.yml` or `docs/docker-compose.yml`

### `service_name` (optional)
- **Type**: `string`
- **Description**: Specific service name to deploy. If not provided, all services in the compose file will be deployed
- **Example**: `mkdocs`, `web`, `api`

### `working_directory` (optional)
- **Type**: `string`
- **Description**: Working directory for docker-compose commands, relative to repository_path. Defaults to repository root
- **Example**: `services/backend`

## Secrets

### `PAT_GITHUB` (optional)
- **Description**: Personal Access Token for accessing private repositories
- **Required**: Only if the workflow repository is private

## How It Works

The workflow executes the following steps:

1. **Log Deployment Start**: Displays all input parameters for debugging
2. **Pull Latest Changes**: Fetches and hard resets to the latest commit
3. **Set Working Directory**: Validates and sets the working directory
4. **Verify Docker Compose File**: Checks that the compose file exists and shows preview
5. **Show Current Status**: Displays currently running containers
6. **Stop Existing Containers**: Gracefully stops running containers
7. **Clean Up Images**: Removes dangling Docker images to free space
8. **Build and Start**: Builds images and starts containers
9. **Wait for Initialization**: Waits 5 seconds for containers to stabilize
10. **Verify Deployment**: Checks that containers are running properly
11. **Show Logs**: Displays recent container logs
12. **Error Handling**: On failure, shows full logs and container status

## Example Workflows

### Deploy Single Service

```yaml
name: Deploy Documentation

on:
  push:
    branches:
      - main
    paths:
      - 'docs/**'
      - 'mkdocs.yml'

jobs:
  deploy-docs:
    uses: 922-Studio/workflows/.github/workflows/deploy-docker.yml@main
    with:
      repository_path: /home/lab/HomeStructure
      docker_compose_file: docker-compose.yml
      service_name: mkdocs
```

### Deploy All Services

```yaml
name: Deploy All Services

on:
  push:
    branches:
      - main

jobs:
  deploy:
    uses: 922-Studio/workflows/.github/workflows/deploy-docker.yml@main
    with:
      repository_path: /home/lab/MyApp
      docker_compose_file: docker-compose.yml
```

### Deploy with Subdirectory

```yaml
name: Deploy Backend

on:
  push:
    branches:
      - main
    paths:
      - 'backend/**'

jobs:
  deploy:
    uses: 922-Studio/workflows/.github/workflows/deploy-docker.yml@main
    with:
      repository_path: /home/lab/MyApp
      docker_compose_file: docker-compose.yml
      working_directory: backend
      service_name: api
```

## Prerequisites

1. **Self-Hosted Runner**: A GitHub self-hosted runner must be installed and running on your server
   ```bash
   # Runner should be configured and started
   sudo ./svc.sh start
   ```

2. **Docker & Docker Compose**: Must be installed on the runner
   ```bash
   docker --version
   docker-compose --version
   ```

3. **Repository Access**: The repository must be cloned to the specified `repository_path`

4. **GitHub Personal Access Token (PAT)**: Required for private repositories
   - Create a PAT at [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
   - Required scopes: `repo` (full control of private repositories)
   - Add as repository secret named `PAT_GITHUB`

5. **Git Configuration**: On the server, ensure the repository is cloned with HTTPS:
   ```bash
   # Check current remote
   git remote -v
   
   # If using SSH (git@github.com), switch to HTTPS
   git remote set-url origin https://github.com/username/repo.git
   ```

6. **Permissions**: The runner user must have:
   - Read/write access to the repository directory
   - Permission to run Docker commands
   - Git configured for the repository

## Logging Format

The workflow uses emojis for quick visual scanning:
- 📥 Pulling/fetching operations
- 🔧 Configuration steps
- 🔍 Verification steps
- 📊 Status displays
- 🛑 Stop operations
- 🧹 Cleanup operations
- 🏗️ Build operations
- ⏳ Wait operations
- ✅ Success indicators
- ❌ Error indicators
- ⚠️ Warnings
- 📋 Log displays

## Troubleshooting

### Git Authentication Fails

If you see `fatal: could not read Username for 'https://github.com': No such device or address`:

1. **Verify PAT_GITHUB secret is set**:
   - Go to repository Settings > Secrets and variables > Actions
   - Ensure `PAT_GITHUB` secret exists

2. **Check git remote URL on server**:
   ```bash
   cd /home/lab/your-repo
   git remote -v
   ```
   
   Should show HTTPS URL:
   ```
   origin  https://github.com/username/repo.git (fetch)
   origin  https://github.com/username/repo.git (push)
   ```
   
   If it shows SSH (`git@github.com`), change to HTTPS:
   ```bash
   git remote set-url origin https://github.com/username/repo.git
   ```

3. **Verify PAT has correct permissions**:
   - Token needs `repo` scope for private repositories

### Deployment Fails
Check the workflow logs - all failures include full container logs and system information.

### Container Not Starting
The workflow shows container logs on failure. Common issues:
- Port conflicts
- Missing environment variables
- Image build failures

### Git Pull Fails
Ensure:
- Repository exists at the specified path
- Runner has git access
- No local changes blocking the pull

## Security Notes

- The workflow uses `git reset --hard` which will discard any local changes
- Container logs may contain sensitive information - review before sharing
- Use secrets for any sensitive configuration values
