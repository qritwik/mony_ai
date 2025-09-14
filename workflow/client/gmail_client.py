import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timezone, timedelta


class GmailClient:
    def __init__(self, access_token, refresh_token, client_id, client_secret):
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        self.service = build("gmail", "v1", credentials=creds)
        self.new_token = creds.token

    def mark_message_as_read(self, message_id):
        """
        Mark a specific Gmail message as read by removing the UNREAD label.
        """
        try:
            self.service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except HttpError as error:
            print(f"An error occurred: {error}")
            raise

    def get_first_email_after(self, epoch_time, query=""):
        """
        Get the very first email strictly after the given epoch_time.
        Returns only 1 email (oldest after epoch), or None if not found.
        """
        query = f"{query} after:{epoch_time}".strip()

        response = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=50)  # small batch
            .execute()
        )

        messages = response.get("messages", [])
        if not messages:
            return None

        emails = []
        for msg in messages:
            message = (
                self.service.users().messages().get(userId="me", id=msg["id"]).execute()
            )

            internal_date = int(message.get("internalDate", 0)) // 1000
            if internal_date <= epoch_time:
                continue

            # Convert internalDate to IST datetime
            ist = timezone(timedelta(hours=5, minutes=30))
            received_dt = datetime.fromtimestamp(internal_date, tz=ist)

            headers = message["payload"]["headers"]
            subject = next(
                (h["value"] for h in headers if h["name"] == "Subject"), "No Subject"
            )
            sender = next(
                (h["value"] for h in headers if h["name"] == "From"), "Unknown"
            )
            date = next((h["value"] for h in headers if h["name"] == "Date"), "Unknown")

            text_body, html_body = self._extract_body(message["payload"])

            emails.append(
                {
                    "id": msg["id"],
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "text_body": text_body,
                    "html_body": html_body,
                    "snippet": message.get("snippet", ""),
                    "labels": message.get("labelIds", []),
                    "internalDate": internal_date,  # epoch (UTC)
                    "email_received_datetime": received_dt,
                }
            )

        if not emails:
            return None

        # Pick the oldest one after epoch
        emails.sort(key=lambda e: e["internalDate"])
        return emails[0]

    def _extract_body(self, payload):
        """Extract both text and HTML body from email"""
        text_body = ""
        html_body = ""

        def decode_data(data):
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode("utf-8")
                except Exception:
                    return ""
            return ""

        if "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                data = part.get("body", {}).get("data")

                if mime_type == "text/plain":
                    text_body = decode_data(data)
                elif mime_type == "text/html":
                    html_body = decode_data(data)

                if "parts" in part:  # handle nested multiparts
                    nested_text, nested_html = self._extract_body(part)
                    if not text_body:
                        text_body = nested_text
                    if not html_body:
                        html_body = nested_html
        else:
            mime_type = payload.get("mimeType", "")
            data = payload.get("body", {}).get("data")

            if mime_type == "text/plain":
                text_body = decode_data(data)
            elif mime_type == "text/html":
                html_body = decode_data(data)

        return text_body, html_body
