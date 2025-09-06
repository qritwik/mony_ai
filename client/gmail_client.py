import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


class GmailClient:
    def __init__(self, access_token, refresh_token, client_id, client_secret):
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )

        if creds.expired:
            creds.refresh(Request())

        self.service = build("gmail", "v1", credentials=creds)
        self.new_token = creds.token

    def get_emails(self, query="", count=10):
        """Get emails with search query and decoded body content"""
        messages = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=count)
            .execute()
            .get("messages", [])
        )

        emails = []
        for msg in messages:
            message = (
                self.service.users().messages().get(userId="me", id=msg["id"]).execute()
            )

            # Extract basic info
            headers = message["payload"]["headers"]
            subject = next(
                (h["value"] for h in headers if h["name"] == "Subject"), "No Subject"
            )
            sender = next(
                (h["value"] for h in headers if h["name"] == "From"), "Unknown"
            )
            date = next((h["value"] for h in headers if h["name"] == "Date"), "Unknown")

            # Extract body content
            text_body, html_body = self._extract_body(message["payload"])

            # Create clean email object
            email_data = {
                "id": msg["id"],
                "subject": subject,
                "from": sender,
                "date": date,
                "text_body": text_body,
                "html_body": html_body,
                "snippet": message["snippet"],
                "labels": message.get("labelIds", []),
            }

            emails.append(email_data)

        return emails

    def _extract_body(self, payload):
        """Extract both text and HTML body from email"""
        text_body = ""
        html_body = ""

        def decode_data(data):
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode("utf-8")
                except:
                    return ""
            return ""

        # Check if email has multiple parts
        if "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                data = part.get("body", {}).get("data")

                if mime_type == "text/plain":
                    text_body = decode_data(data)
                elif mime_type == "text/html":
                    html_body = decode_data(data)

                # Handle nested parts (like multipart/alternative)
                if "parts" in part:
                    nested_text, nested_html = self._extract_body(part)
                    if not text_body:
                        text_body = nested_text
                    if not html_body:
                        html_body = nested_html
        else:
            # Single part email
            mime_type = payload.get("mimeType", "")
            data = payload.get("body", {}).get("data")

            if mime_type == "text/plain":
                text_body = decode_data(data)
            elif mime_type == "text/html":
                html_body = decode_data(data)

        return text_body, html_body
