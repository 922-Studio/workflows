# AI-Powered Versioning Workflow

This repository contains a reusable GitHub Actions workflow to automate semantic versioning using Google's Gemini API. It analyzes commit messages to determine the next version number, updates a `version.txt` file, and creates a new version tag.

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
