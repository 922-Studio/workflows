# Send Email Notification Workflow

A reusable GitHub Actions workflow for sending email notifications via Gmail SMTP. This workflow supports both default workflow status templates and custom HTML email bodies.

## Features

- 📧 Send emails to multiple recipients
- 🎨 Clean, responsive default HTML template for workflow notifications
- ✨ Support for custom HTML email bodies
- 🔄 Automatic retry and error handling (continues on failure, reports at end)
- 🎯 Dynamic workflow status indicators (success, failure, cancelled)
- 🔐 Secure authentication using Gmail App Passwords

## Prerequisites

### 1. Gmail App Password

You need to generate a Gmail App Password to use this workflow:

1. Go to your [Google Account](https://myaccount.google.com/)
2. Navigate to **Security** → **2-Step Verification** (you must have 2FA enabled)
3. Scroll down to **App passwords**
4. Generate a new app password for "Mail"
5. Copy the 16-character password

### 2. Add Secret to Repository

In your workflows repository (922-Studio/workflows):

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `GMAIL_APP_PASSWORD`
4. Value: Your 16-character app password
5. Click **Add secret**

Since the app password is stored in the workflows repository, you don't need to pass it when calling the workflow from other repositories.

## Usage

### Basic Usage (Default Template)

To send workflow status notifications with the default template:

```yaml
name: Notify on Deployment

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - name: Deploy application
        run: |
          # Your deployment steps here
          echo "Deploying..."

  notify:
    needs: deploy
    if: always()
    uses: 922-Studio/workflows/.github/workflows/send-email.yml@main
    with:
      recipients: '["admin@example.com", "team@example.com"]'
      subject: "Deployment Status: ${{ needs.deploy.result }}"
      workflow_status: "${{ needs.deploy.result }}"
      workflow_name: "${{ github.workflow }}"
      repository_name: "${{ github.repository }}"
      run_url: "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
    secrets:
      GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}
```

### Custom HTML Template

To send emails with a custom HTML body:

```yaml
jobs:
  send-custom-email:
    uses: 922-Studio/workflows/.github/workflows/send-email.yml@main
    with:
      recipients: '["user1@example.com", "user2@example.com"]'
      subject: "Custom Notification"
      sender_name: "My Custom Bot"
      custom_body_html: |
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background-color: #4CAF50; color: white; padding: 20px; text-align: center; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Custom Notification</h1>
                </div>
                <p>This is a custom email with your own HTML template.</p>
            </div>
        </body>
        </html>
    secrets:
      GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}
```

### Conditional Notifications

Send emails only on failure:

```yaml
jobs:
  build:
    runs-on: self-hosted
    steps:
      - name: Build application
        run: make build

  notify-on-failure:
    needs: build
    if: failure()
    uses: 922-Studio/workflows/.github/workflows/send-email.yml@main
    with:
      recipients: '["oncall@example.com"]'
      subject: "🚨 Build Failed: ${{ github.repository }}"
      workflow_status: "failure"
      workflow_name: "${{ github.workflow }}"
      repository_name: "${{ github.repository }}"
      run_url: "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
    secrets:
      GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}
```

## Input Parameters

### Required Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `recipients` | string | JSON array of email addresses (e.g., `["email1@example.com", "email2@example.com"]`) |
| `subject` | string | Email subject line |

### Optional Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sender_name` | string | "Home-Lab Bot" | Display name for the sender |
| `custom_body_html` | string | - | Custom HTML body for the email (overrides default template) |
| `workflow_status` | string | - | Status of the workflow (success, failure, cancelled) - used in default template |
| `workflow_name` | string | - | Name of the workflow - used in default template |
| `repository_name` | string | - | Repository name - used in default template |
| `run_url` | string | - | URL to the workflow run - used in default template |

### Required Secrets

| Secret | Description |
|--------|-------------|
| `GMAIL_APP_PASSWORD` | Gmail App Password for SMTP authentication (stored in workflows repo) |
| `PAT_GITHUB` | Personal Access Token for cloning private repos (optional) |

## Default Email Template

The default template provides a clean, professional look with:

- ✅ Color-coded status headers (green for success, red for failure, gray for cancelled)
- 📊 Workflow information table (workflow name, repository, status)
- 🔗 Direct link to the workflow run
- 📱 Responsive design that works on mobile and desktop
- 🎨 Modern styling with rounded corners and shadows

### Status Colors

- **Success**: Green (#28a745) with ✅ emoji
- **Failure**: Red (#dc3545) with ❌ emoji
- **Cancelled**: Gray (#6c757d) with ⚠️ emoji
- **Other**: Blue (#007bff) with ℹ️ emoji

## Error Handling

The workflow implements robust error handling:

1. **Validation**: All required inputs are validated before sending
2. **Retry Logic**: Each recipient is processed independently
3. **Continue on Failure**: If one email fails, the workflow continues to send to other recipients
4. **Final Status**: The workflow fails at the end if any emails could not be sent
5. **Detailed Logging**: Success and failure counts are logged with recipient details

## Examples

### Multi-Stage Deployment with Notifications

```yaml
name: Deploy and Notify

on:
  push:
    branches:
      - main

jobs:
  version:
    uses: 922-Studio/workflows/.github/workflows/versioning.yml@main
    secrets:
      gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}

  deploy:
    needs: version
    uses: 922-Studio/workflows/.github/workflows/deploy-docker.yml@main
    with:
      repository_path: "/home/runner/my-app"
      docker_compose_file: "docker-compose.yml"
      service_name: "api"
    secrets:
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}

  notify-success:
    needs: [version, deploy]
    if: success()
    uses: 922-Studio/workflows/.github/workflows/send-email.yml@main
    with:
      recipients: '["team@example.com"]'
      subject: "✅ Deployment Successful - Version ${{ needs.version.outputs.new_version }}"
      workflow_status: "success"
      workflow_name: "Deploy and Notify"
      repository_name: "${{ github.repository }}"
      run_url: "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
    secrets:
      GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}

  notify-failure:
    needs: [version, deploy]
    if: failure()
    uses: 922-Studio/workflows/.github/workflows/send-email.yml@main
    with:
      recipients: '["oncall@example.com", "devops@example.com"]'
      subject: "❌ Deployment Failed - Immediate Action Required"
      workflow_status: "failure"
      workflow_name: "Deploy and Notify"
      repository_name: "${{ github.repository }}"
      run_url: "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
    secrets:
      GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
      PAT_GITHUB: ${{ secrets.PAT_GITHUB }}
```

## Troubleshooting

### Email Not Sending

1. **Check App Password**: Ensure your Gmail App Password is correct and stored as a secret
2. **2FA Enabled**: Gmail requires 2-Factor Authentication to generate app passwords
3. **SMTP Access**: Verify Gmail SMTP (smtp.gmail.com:465) is accessible from your runner
4. **Firewall**: Check if port 465 is blocked by your network/firewall

### Invalid Recipients Format

Ensure recipients are in valid JSON array format:
- ✅ Correct: `'["email@example.com"]'`
- ❌ Wrong: `"email@example.com"`
- ❌ Wrong: `["email@example.com"]` (missing quotes around the array)

### Custom HTML Not Rendering

- Ensure your HTML is valid
- Some email clients have limited CSS support (use inline styles)
- Test your HTML template with email testing tools

## Security Notes

- 🔐 Never commit your Gmail App Password to git
- 🔒 Always use GitHub Secrets to store sensitive credentials
- 🛡️ The app password has limited scope (mail only) compared to your main password
- 🔑 You can revoke app passwords at any time from your Google Account settings

## Sender Configuration

The sender email is hardcoded to `gregor160505@gmail.com` in the workflow. If you need to change this:

1. Edit `.github/workflows/send-email.yml`
2. Modify the `SENDER_EMAIL` environment variable
3. Ensure you have the corresponding Gmail App Password

## Support

For issues or questions about this workflow, please open an issue in the workflows repository.
