# Versioning Workflow Details

This document provides a detailed explanation of the AI-Powered Versioning workflow.

<details>
<summary>Workflow Inputs</summary>

### `gemini_api_key` (required)

*   **Description:** This is your secret API key for the Google Gemini API. The workflow uses this key to securely authenticate and analyze your commit messages.
*   **Type:** `string`
*   **How to create:** You can generate a new API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
*   **How to store:** For security, this key should be stored as a secret in the repository that *uses* this workflow. Navigate to `Settings > Secrets and variables > Actions` and add a new repository secret named `GEMINI_API_KEY`.

</details>

<details>
<summary>Workflow Outputs</summary>

### `new_version`

*   **Description:** The newly calculated version number (e.g., `1.2.3`). This output can be passed to subsequent jobs in your workflow.
*   **Type:** `string`
*   **Example Usage:** You can use this output to tag a Docker image in a later step.
    ```yaml
    jobs:
      version:
        uses: <your-username>/<this-repo-name>/.github/workflows/versioning.yml@main
        with:
          gemini_api_key: ${{ secrets.GEMINI_API_KEY }}

      build-and-push-docker:
        needs: version
        runs-on: ubuntu-latest
        steps:
          - name: Build and push Docker image
            uses: docker/build-push-action@v5
            with:
              push: true
              tags: my-image:${{ needs.version.outputs.new_version }}
    ```

</details>

<details>
<summary>Versioning Logic</summary>

The core of the versioning process is the `.github/scripts/determine_version.py` script, which follows these steps:

1.  **Read Current Version:** The script first looks for a `version.txt` file in the root of your repository.
    *   If found, it reads the version number from it.
    *   If not found, it defaults to an initial version of `0.1.0`.

2.  **Analyze Commits with Gemini:** The script sends the collected commit messages to the Gemini 1.5 Flash model with a carefully engineered prompt. This prompt instructs the AI to act as an expert in **Conventional Commits** and determine the version bump based on the following rules:
    *   **MAJOR:** If any commit message contains `BREAKING CHANGE:` in its body.
    *   **MINOR:** If any commit message starts with `feat:`.
    *   **PATCH:** If any commit message starts with `fix:`.

3.  **Handle API Failures:** If the call to the Gemini API fails for any reason (e.g., network issues, invalid key), the script will default to a `PATCH` version bump to ensure the workflow doesn't fail unexpectedly.

4.  **Calculate Next Version:** Based on the bump level (`MAJOR`, `MINOR`, or `PATCH`), the script increments the appropriate part of the version number.

</details>

<details>
<summary>Skipping a Version Bump</summary>

If you want to push changes to your `main` branch without triggering a new version (for example, when updating documentation or other non-code assets), you can include `[ci skip]` anywhere in your commit message. The workflow will detect this and gracefully exit without creating a new version.

</details>
