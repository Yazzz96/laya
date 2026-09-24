"""Minimal Gmail API access. Reads by default; the only write is removing the INBOX label.

There is intentionally no delete or trash call anywhere in this module.
Setup: create an OAuth "Desktop app" client in Google Cloud, enable the Gmail API, and save
the JSON as credentials.json. The first run opens a browser to sign in; the token is cached.
"""
import base64
import os
from html import unescape
import re
from typing import Any, Dict, Iterator, List

READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
_WANTED = ("From", "To", "Subject", "Date", "List-Unsubscribe", "List-Id", "Precedence")


def connect(credentials: str = "credentials.json", token: str = "token.json", write: bool = False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    scopes = [MODIFY_SCOPE] if write else [READ_SCOPE]
    token = token.replace(".json", "-write.json") if write else token
    creds = Credentials.from_authorized_user_file(token, scopes) if os.path.exists(token) else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(credentials, scopes).run_local_server(port=0)
        with open(token, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _text(payload: Dict[str, Any]) -> str:
    """Prefer text/plain; fall back to stripped text/html."""
    plain, html = [], []

    def walk(part):
        data = part.get("body", {}).get("data")
        mime = part.get("mimeType", "")
        if data:
            raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
            (plain if mime == "text/plain" else html if mime == "text/html" else []).append(raw)
        for p in part.get("parts", []) or []:
            walk(p)

    walk(payload)
    if plain:
        return "\n".join(plain)
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", "\n".join(html))
    return unescape(re.sub(r"<[^>]+>", " ", text))


def parse_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", []) if h["name"] in _WANTED}
    return {"id": msg["id"], "thread_id": msg.get("threadId"), "labels": msg.get("labelIds", []),
            "headers": headers, "from": headers.get("From", ""), "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""), "body": _text(msg.get("payload", {})) or msg.get("snippet", "")}


def inbox_messages(service, query: str = "in:inbox", limit: int = 500) -> Iterator[Dict[str, Any]]:
    token, seen = None, 0
    while seen < limit:
        resp = service.users().messages().list(userId="me", q=query, pageToken=token,
                                               maxResults=min(100, limit - seen)).execute()
        for ref in resp.get("messages", []):
            msg = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
            seen += 1
            yield parse_message(msg)
        token = resp.get("nextPageToken")
        if not token:
            break


def archive(service, ids: List[str]) -> int:
    """Remove the INBOX label (Gmail's Archive). Emails stay in All Mail."""
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i + 1000]
        service.users().messages().batchModify(userId="me", body={"ids": chunk, "removeLabelIds": ["INBOX"]}).execute()
    return len(ids)
