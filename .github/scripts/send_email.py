#!/usr/bin/env python3
"""
Send email notifications via Gmail SMTP.
Supports custom HTML templates and default workflow status template.
"""

import os
import sys
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


def get_default_template():
    """Return the default HTML email template with workflow status."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Workflow Notification</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f5f5f5;">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 30px 40px; text-align: center; background-color: {status_color}; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">{status_emoji} Workflow {status_text}</h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 20px; color: #333333; font-size: 16px; line-height: 1.5;">
                                Your workflow has completed with status: <strong>{workflow_status}</strong>
                            </p>
                            
                            <table role="presentation" style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                                <tr>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #eeeeee;">
                                        <strong style="color: #666666; font-size: 14px;">Workflow:</strong>
                                    </td>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #eeeeee; text-align: right;">
                                        <span style="color: #333333; font-size: 14px;">{workflow_name}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #eeeeee;">
                                        <strong style="color: #666666; font-size: 14px;">Repository:</strong>
                                    </td>
                                    <td style="padding: 12px 0; border-bottom: 1px solid #eeeeee; text-align: right;">
                                        <span style="color: #333333; font-size: 14px;">{repository_name}</span>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 12px 0;">
                                        <strong style="color: #666666; font-size: 14px;">Status:</strong>
                                    </td>
                                    <td style="padding: 12px 0; text-align: right;">
                                        <span style="color: {status_color}; font-size: 14px; font-weight: 600;">{workflow_status}</span>
                                    </td>
                                </tr>
                            </table>
                            
                            {run_url_section}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; text-align: center; background-color: #f8f9fa; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; color: #888888; font-size: 12px;">
                                This is an automated notification from your Home-Lab Bot
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def build_default_html_body(workflow_status, workflow_name, repository_name, run_url):
    """Build the default HTML body with workflow information."""
    template = get_default_template()
    
    # Determine status styling
    status = workflow_status.lower() if workflow_status else "unknown"
    
    if status == "success":
        status_color = "#28a745"
        status_emoji = "✅"
        status_text = "Successful"
    elif status == "failure":
        status_color = "#dc3545"
        status_emoji = "❌"
        status_text = "Failed"
    elif status == "cancelled":
        status_color = "#6c757d"
        status_emoji = "⚠️"
        status_text = "Cancelled"
    else:
        status_color = "#007bff"
        status_emoji = "ℹ️"
        status_text = "Completed"
    
    # Build run URL section if provided
    run_url_section = ""
    if run_url:
        run_url_section = f"""
            <div style="margin-top: 30px; text-align: center;">
                <a href="{run_url}" style="display: inline-block; padding: 12px 24px; background-color: #007bff; color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: 600; font-size: 14px;">
                    View Workflow Run
                </a>
            </div>
        """
    
    # Replace placeholders
    html_body = template.format(
        status_color=status_color,
        status_emoji=status_emoji,
        status_text=status_text,
        workflow_status=workflow_status or "Unknown",
        workflow_name=workflow_name or "N/A",
        repository_name=repository_name or "N/A",
        run_url_section=run_url_section
    )
    
    return html_body


def send_email(sender_email, sender_name, app_password, recipient, subject, html_body):
    """Send an email via Gmail SMTP."""
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{sender_name} <{sender_email}>"
        message["To"] = recipient
        
        # Attach HTML body
        html_part = MIMEText(html_body, "html")
        message.attach(html_part)
        
        # Connect to Gmail SMTP server
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.send_message(message)
        
        print(f"✅ Email sent successfully to: {recipient}")
        return True
    
    except Exception as e:
        print(f"❌ Failed to send email to {recipient}: {str(e)}")
        return False


def main():
    """Main function to send emails."""
    # Get environment variables
    sender_email = os.getenv("SENDER_EMAIL")
    sender_name = os.getenv("SENDER_NAME", "Home-Lab Bot")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    recipients_json = os.getenv("RECIPIENTS")
    subject = os.getenv("SUBJECT")
    custom_body_html = os.getenv("CUSTOM_BODY_HTML")
    workflow_status = os.getenv("WORKFLOW_STATUS")
    workflow_name = os.getenv("WORKFLOW_NAME")
    repository_name = os.getenv("REPOSITORY_NAME")
    run_url = os.getenv("RUN_URL")
    
    # Validate required inputs
    if not sender_email:
        print("❌ ERROR: SENDER_EMAIL is not set")
        sys.exit(1)
    
    if not app_password:
        print("❌ ERROR: GMAIL_APP_PASSWORD is not set")
        sys.exit(1)
    
    if not recipients_json:
        print("❌ ERROR: RECIPIENTS is not set")
        sys.exit(1)
    
    if not subject:
        print("❌ ERROR: SUBJECT is not set")
        sys.exit(1)
    
    # Parse recipients JSON array
    try:
        recipients = json.loads(recipients_json)
        if not isinstance(recipients, list) or len(recipients) == 0:
            print("❌ ERROR: RECIPIENTS must be a non-empty JSON array")
            sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Failed to parse RECIPIENTS JSON: {str(e)}")
        sys.exit(1)
    
    # Determine HTML body to use
    if custom_body_html:
        html_body = custom_body_html
        print("📝 Using custom HTML body")
    else:
        html_body = build_default_html_body(
            workflow_status, 
            workflow_name, 
            repository_name, 
            run_url
        )
        print("📝 Using default HTML template")
    
    # Send emails to all recipients
    print(f"📧 Sending emails to {len(recipients)} recipient(s)...")
    success_count = 0
    failure_count = 0
    failed_recipients = []
    
    for recipient in recipients:
        if send_email(sender_email, sender_name, app_password, recipient, subject, html_body):
            success_count += 1
        else:
            failure_count += 1
            failed_recipients.append(recipient)
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"📊 Email Summary:")
    print(f"   ✅ Successful: {success_count}")
    print(f"   ❌ Failed: {failure_count}")
    if failed_recipients:
        print(f"   Failed recipients: {', '.join(failed_recipients)}")
    print("=" * 50)
    
    # Exit with error if any emails failed
    if failure_count > 0:
        print(f"\n❌ Workflow failed: {failure_count} email(s) could not be sent")
        sys.exit(1)
    else:
        print(f"\n✅ All emails sent successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
