"""
Gmail Sender: Sends email with report attachment via Gmail API.

Uses OAuth2 authentication. On first run, opens a browser window for Google
consent. Subsequent runs use the saved token.json for automatic authentication.

Usage:
    python tools/gmail_sender.py
    python tools/gmail_sender.py --attachment path/to/report.pdf --to user@example.com
"""

import os
import sys
import json
import base64
import mimetypes
import argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate(credentials_file: str, token_file: str) -> Credentials:
    """
    Authenticate with Gmail API via OAuth2.

    First run opens a browser for consent. Token is saved for reuse.
    """
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                # Token refresh failed — need fresh auth
                creds = None

        if not creds:
            if not os.path.exists(credentials_file):
                raise FileNotFoundError(
                    f"OAuth credentials not found at '{credentials_file}'. "
                    "Download credentials.json from Google Cloud Console "
                    "(APIs & Services > Credentials > OAuth 2.0 Client IDs)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future runs
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print(f"  Token saved to {token_file}")

    return creds


# ---------------------------------------------------------------------------
# Email construction
# ---------------------------------------------------------------------------

def build_email(sender: str, recipient: str, subject: str,
                body_html: str, attachment_path: str = None) -> dict:
    """
    Build a MIME email message with optional attachment.

    Returns a dict with base64url-encoded 'raw' field ready for Gmail API.
    """
    message = MIMEMultipart()
    message["to"] = recipient
    message["from"] = sender
    message["subject"] = subject

    # HTML body
    message.attach(MIMEText(body_html, "html"))

    # Attachment
    if attachment_path and os.path.exists(attachment_path):
        content_type, _ = mimetypes.guess_type(attachment_path)
        if content_type is None:
            content_type = "application/octet-stream"
        main_type, sub_type = content_type.split("/", 1)

        with open(attachment_path, "rb") as f:
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(f.read())

        encoders.encode_base64(attachment)
        filename = os.path.basename(attachment_path)
        attachment.add_header("Content-Disposition", "attachment", filename=filename)
        message.attach(attachment)

        file_size_mb = os.path.getsize(attachment_path) / (1024 * 1024)
        if file_size_mb > 25:
            print(f"  WARNING: Attachment is {file_size_mb:.1f} MB — Gmail limit is 25 MB")

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


def generate_email_content(analysis_path: str) -> tuple:
    """
    Generate email subject and HTML body from analysis results.

    Returns:
        (subject, body_html) tuple
    """
    # Load analysis for summary bullets
    summary_bullets = []
    date_from = "?"
    date_to = "?"
    total_videos = 0

    if analysis_path and os.path.exists(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)
        summary_bullets = analysis.get("executive_summary", [])
        period = analysis.get("data_period", {})
        date_from = period.get("from", "?")
        date_to = period.get("to", "?")
        total_videos = analysis.get("total_videos_analyzed", 0)

    subject = f"AI YouTube Trend Report — {date_from} to {date_to}"

    bullets_html = ""
    for bullet in summary_bullets:
        bullets_html += f"<li style='margin-bottom: 8px; color: #333;'>{bullet}</li>\n"

    body_html = f"""
    <div style="font-family: Calibri, Arial, sans-serif; max-width: 650px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #0F96F0, #00D2FF); padding: 24px 32px; border-radius: 8px 8px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">AI YouTube Trend Analysis</h1>
            <p style="color: rgba(255,255,255,0.85); margin: 8px 0 0 0; font-size: 14px;">
                {date_from} to {date_to} &nbsp;|&nbsp; {total_videos} videos analyzed
            </p>
        </div>

        <div style="background: #f8f9fa; padding: 24px 32px; border: 1px solid #e9ecef;">
            <h2 style="color: #1a1a2e; font-size: 18px; margin-top: 0;">Key Highlights</h2>
            <ul style="padding-left: 20px; line-height: 1.8;">
                {bullets_html}
            </ul>
        </div>

        <div style="background: #ffffff; padding: 24px 32px; border: 1px solid #e9ecef; border-radius: 0 0 8px 8px;">
            <p style="color: #555; font-size: 14px; margin: 0;">
                The full report is attached as a PDF with detailed charts,
                tables, and actionable recommendations.
            </p>
            <hr style="border: none; border-top: 1px solid #e9ecef; margin: 16px 0;">
            <p style="color: #999; font-size: 12px; margin: 0;">
                This report was generated automatically by the WAT Framework.
            </p>
        </div>
    </div>
    """

    return subject, body_html


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_email(service, message: dict) -> dict:
    """Send the email via Gmail API and return the message metadata."""
    result = service.users().messages().send(userId="me", body=message).execute()
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(attachment_path: str = None, recipient_email: str = None,
         subject: str = None, body_html: str = None) -> dict:
    """
    Send the trend analysis report via Gmail.

    Args:
        attachment_path: Path to report file (.pdf). Defaults to latest from manifest.
        recipient_email: Recipient email. Defaults to GMAIL_RECIPIENT_EMAIL from .env.
        subject: Email subject. Auto-generated if not provided.
        body_html: Email HTML body. Auto-generated if not provided.

    Returns:
        dict with status and message metadata.
    """
    load_dotenv()

    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
    sender_email = os.getenv("GMAIL_SENDER_EMAIL", "")

    # Resolve to absolute paths relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isabs(credentials_file):
        credentials_file = os.path.join(project_root, credentials_file)
    if not os.path.isabs(token_file):
        token_file = os.path.join(project_root, token_file)

    if recipient_email is None:
        recipient_email = os.getenv("GMAIL_RECIPIENT_EMAIL", "")

    if not recipient_email:
        return {"status": "error", "error": "No recipient email. Set GMAIL_RECIPIENT_EMAIL in .env."}

    if not sender_email:
        return {"status": "error", "error": "No sender email. Set GMAIL_SENDER_EMAIL in .env."}

    tmp_dir = os.path.join(project_root, ".tmp")

    try:
        # Resolve attachment from manifest if not provided
        analysis_path = None
        if attachment_path is None:
            manifest_path = os.path.join(tmp_dir, "youtube_latest.json")
            if not os.path.exists(manifest_path):
                return {"status": "error",
                        "error": "No manifest found. Run the full pipeline first."}

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            attachment_path = manifest.get("latest_report", {}).get("report_file")
            analysis_path = manifest.get("latest_analysis", {}).get("analysis_file")

            if not attachment_path or not os.path.exists(attachment_path):
                return {"status": "error",
                        "error": f"Report file not found: {attachment_path}. Generate the PDF report first."}

        # Generate email content if not provided
        if subject is None or body_html is None:
            gen_subject, gen_body = generate_email_content(analysis_path)
            subject = subject or gen_subject
            body_html = body_html or gen_body

        # Authenticate
        print("  Authenticating with Gmail ...")
        creds = authenticate(credentials_file, token_file)
        service = build("gmail", "v1", credentials=creds)

        # Build and send email
        print(f"  Building email to {recipient_email} ...")
        message = build_email(sender_email, recipient_email, subject,
                              body_html, attachment_path)

        print("  Sending ...")
        result = send_email(service, message)
        message_id = result.get("id", "unknown")
        print(f"  Email sent successfully. Message ID: {message_id}")

        return {
            "status": "success",
            "data": {
                "message_id": message_id,
                "recipient": recipient_email,
                "subject": subject,
                "attachment": os.path.basename(attachment_path) if attachment_path else None,
            },
        }

    except FileNotFoundError as e:
        return {"status": "error", "error": str(e)}
    except HttpError as e:
        return {"status": "error", "error": f"Gmail API error: {e}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gmail Report Sender")
    parser.add_argument("--attachment", type=str, help="Path to report file (.pdf) to attach")
    parser.add_argument("--to", type=str, help="Recipient email address")
    parser.add_argument("--subject", type=str, help="Custom email subject")
    args = parser.parse_args()

    result = main(attachment_path=args.attachment, recipient_email=args.to,
                  subject=args.subject)

    if result["status"] == "success":
        print(f"\nSuccess: Email sent to {result['data']['recipient']}")
        print(f"  Subject: {result['data']['subject']}")
        print(f"  Message ID: {result['data']['message_id']}")
        sys.exit(0)
    else:
        print(f"\nError: {result['error']}", file=sys.stderr)
        sys.exit(1)
