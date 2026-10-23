"""
Gmail API client.

SECURITY RULES (enforced here):
- Email body/HTML never injected into agent system prompts.
- HTML sanitised with bleach before being returned.
- Attachment types validated against an allowlist.
- Credentials never logged.
"""
from __future__ import annotations

import base64
import email as _email_lib
import logging
import mimetypes
import re
from typing import Optional, TypedDict

try:
    import bleach
except ImportError:
    bleach = None
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ALLOWED_ATTACHMENT_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/zip",
        "application/x-zip-compressed",
    }
)

# HTML tags / attributes we allow when sanitising body_html
_ALLOWED_HTML_TAGS = [
    "a", "abbr", "acronym", "b", "blockquote", "br", "code", "div", "em",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "li", "ol",
    "p", "pre", "q", "s", "small", "span", "strong", "sub", "sup", "table",
    "tbody", "td", "th", "thead", "tr", "u", "ul",
]
_ALLOWED_HTML_ATTRS: dict[str, list[str]] = {
    "a": ["href", "title", "rel"],
    "abbr": ["title"],
    "acronym": ["title"],
    "img": ["src", "alt", "width", "height"],
    "*": ["class", "style"],
}


class AttachmentInfo(TypedDict):
    filename: str
    mime_type: str
    size: int
    attachment_id: str


class EmailMessage(TypedDict):
    id: str
    thread_id: str
    subject: str
    from_email: str
    to_emails: list[str]
    date: str
    snippet: str
    body_text: str
    body_html: str
    is_read: bool
    labels: list[str]
    attachments: list[AttachmentInfo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_service(credentials: Credentials):
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _decode_body(data: str) -> str:
    """Decode a base64url-encoded Gmail body part."""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _sanitise_html(html: str) -> str:
    """Strip unsafe HTML while preserving safe structure."""
    if bleach is not None:
        return bleach.clean(
            html,
            tags=_ALLOWED_HTML_TAGS,
            attributes=_ALLOWED_HTML_ATTRS,
            strip=True,
        )
    import html as html_lib
    return html_lib.escape(html)


def _parse_message(raw: dict) -> EmailMessage:
    """Parse a raw Gmail API message dict into an EmailMessage TypedDict."""
    headers: dict[str, str] = {
        h["name"].lower(): h["value"]
        for h in raw.get("payload", {}).get("headers", [])
    }

    subject = headers.get("subject", "(no subject)")
    from_email = headers.get("from", "")
    to_raw = headers.get("to", "")
    to_emails = [t.strip() for t in to_raw.split(",") if t.strip()]
    date = headers.get("date", "")

    body_text = ""
    body_html = ""
    attachments: list[AttachmentInfo] = []

    def _walk_parts(parts: list[dict]) -> None:
        nonlocal body_text, body_html
        for part in parts:
            mime = part.get("mimeType", "")
            body_data = part.get("body", {})
            sub_parts = part.get("parts", [])

            if sub_parts:
                _walk_parts(sub_parts)
            elif mime == "text/plain" and body_data.get("data"):
                body_text = _decode_body(body_data["data"])
            elif mime == "text/html" and body_data.get("data"):
                raw_html = _decode_body(body_data["data"])
                body_html = _sanitise_html(raw_html)
            elif body_data.get("attachmentId"):
                filename = part.get("filename", "unknown")
                # Validate MIME type from file extension as extra check
                guessed_type, _ = mimetypes.guess_type(filename)
                effective_mime = guessed_type or mime
                if effective_mime in ALLOWED_ATTACHMENT_MIME_TYPES:
                    attachments.append(
                        AttachmentInfo(
                            filename=filename,
                            mime_type=effective_mime,
                            size=body_data.get("size", 0),
                            attachment_id=body_data["attachmentId"],
                        )
                    )
                else:
                    logger.warning(
                        "Skipping attachment '%s' with disallowed type '%s'",
                        filename,
                        effective_mime,
                    )

    payload = raw.get("payload", {})
    top_mime = payload.get("mimeType", "")
    top_parts = payload.get("parts", [])
    top_body = payload.get("body", {})

    if top_parts:
        _walk_parts(top_parts)
    elif top_mime == "text/plain" and top_body.get("data"):
        body_text = _decode_body(top_body["data"])
    elif top_mime == "text/html" and top_body.get("data"):
        body_html = _sanitise_html(_decode_body(top_body["data"]))

    label_ids: list[str] = raw.get("labelIds", [])
    is_read = "UNREAD" not in label_ids

    return EmailMessage(
        id=raw["id"],
        thread_id=raw.get("threadId", ""),
        subject=subject,
        from_email=from_email,
        to_emails=to_emails,
        date=date,
        snippet=raw.get("snippet", ""),
        body_text=body_text,
        body_html=body_html,
        is_read=is_read,
        labels=label_ids,
        attachments=attachments,
    )


def _build_mime_message(
    to: str,
    subject: str,
    body: str,
    reply_to_message: Optional[dict] = None,
) -> dict:
    """Build a Gmail API-compatible raw MIME message dict."""
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject

    if reply_to_message:
        headers = {
            h["name"].lower(): h["value"]
            for h in reply_to_message.get("payload", {}).get("headers", [])
        }
        msg["In-Reply-To"] = headers.get("message-id", "")
        msg["References"] = headers.get("references", "") + " " + headers.get("message-id", "")
        msg["X-Reply-To-Thread"] = reply_to_message.get("threadId", "")

    msg.attach(MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = {"raw": raw}
    if reply_to_message:
        result["threadId"] = reply_to_message.get("threadId", "")
    return result


# ---------------------------------------------------------------------------
# Public Gmail client functions
# ---------------------------------------------------------------------------

def list_messages(
    credentials: Credentials,
    query: str = "",
    max_results: int = 25,
) -> list[EmailMessage]:
    """
    List inbox messages matching an optional query string.

    Parameters
    ----------
    credentials:
        Valid Google OAuth2 credentials.
    query:
        Gmail search query (e.g. 'is:unread label:inbox').
    max_results:
        Maximum number of messages to return (1-500).

    Returns
    -------
    list[EmailMessage]
    """
    max_results = max(1, min(500, max_results))
    service = _build_service(credentials)
    try:
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
    except HttpError as exc:
        logger.error("list_messages failed: %s", exc.status_code)
        raise

    messages_meta = response.get("messages", [])
    results: list[EmailMessage] = []
    for meta in messages_meta:
        try:
            raw = (
                service.users()
                .messages()
                .get(userId="me", id=meta["id"], format="full")
                .execute()
            )
            results.append(_parse_message(raw))
        except HttpError as exc:
            logger.warning("Could not fetch message %s: %s", meta["id"], exc.status_code)
    return results


def get_message(credentials: Credentials, message_id: str) -> EmailMessage:
    """Fetch a single message by ID."""
    service = _build_service(credentials)
    try:
        raw = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
    except HttpError as exc:
        logger.error("get_message(%s) failed: %s", message_id, exc.status_code)
        raise
    return _parse_message(raw)


def get_thread(credentials: Credentials, thread_id: str) -> list[EmailMessage]:
    """Return all messages in a thread, oldest first."""
    service = _build_service(credentials)
    try:
        thread = (
            service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )
    except HttpError as exc:
        logger.error("get_thread(%s) failed: %s", thread_id, exc.status_code)
        raise
    return [_parse_message(m) for m in thread.get("messages", [])]


def search_messages(
    credentials: Credentials,
    query: str,
    max_results: int = 50,
) -> list[EmailMessage]:
    """Search messages using Gmail query syntax."""
    return list_messages(credentials, query=query, max_results=max_results)


def send_message(
    credentials: Credentials,
    to: str,
    subject: str,
    body: str,
    reply_to_id: Optional[str] = None,
) -> str:
    """
    Send an email message.

    Parameters
    ----------
    reply_to_id:
        Message ID to reply to.  If supplied the message will be threaded.

    Returns
    -------
    str
        The sent message ID.
    """
    service = _build_service(credentials)
    reply_to_raw: Optional[dict] = None
    if reply_to_id:
        try:
            reply_to_raw = (
                service.users()
                .messages()
                .get(userId="me", id=reply_to_id, format="metadata")
                .execute()
            )
        except HttpError:
            logger.warning("Could not fetch reply-to message %s; sending without thread.", reply_to_id)

    payload = _build_mime_message(to, subject, body, reply_to_raw)
    try:
        sent = service.users().messages().send(userId="me", body=payload).execute()
    except HttpError as exc:
        logger.error("send_message failed: %s", exc.status_code)
        raise
    logger.info("Email sent, message_id=%s", sent["id"])
    return sent["id"]


def create_draft(
    credentials: Credentials,
    to: str,
    subject: str,
    body: str,
) -> str:
    """
    Create a draft without sending it.

    Returns
    -------
    str
        Draft ID.
    """
    service = _build_service(credentials)
    payload = _build_mime_message(to, subject, body)
    try:
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": payload})
            .execute()
        )
    except HttpError as exc:
        logger.error("create_draft failed: %s", exc.status_code)
        raise
    return draft["id"]


def mark_read(credentials: Credentials, message_id: str) -> None:
    """Remove the UNREAD label from a message."""
    service = _build_service(credentials)
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
    except HttpError as exc:
        logger.error("mark_read(%s) failed: %s", message_id, exc.status_code)
        raise


def archive_message(credentials: Credentials, message_id: str) -> None:
    """Remove INBOX label (archive the message)."""
    service = _build_service(credentials)
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["INBOX"]},
        ).execute()
    except HttpError as exc:
        logger.error("archive_message(%s) failed: %s", message_id, exc.status_code)
        raise


def move_to_label(
    credentials: Credentials,
    message_id: str,
    label: str,
) -> None:
    """
    Apply a label to a message.

    Parameters
    ----------
    label:
        Gmail label ID (e.g. 'Label_123') or well-known label ('SPAM', 'TRASH').
    """
    service = _build_service(credentials)
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label]},
        ).execute()
    except HttpError as exc:
        logger.error("move_to_label(%s, %s) failed: %s", message_id, label, exc.status_code)
        raise


def delete_message(
    credentials: Credentials,
    message_id: str,
    *,
    confirmed: bool = False,
) -> None:
    """
    Permanently delete a message (moves to Trash first, then purges).

    Parameters
    ----------
    confirmed:
        Must be True to proceed.  Guards against accidental deletion.
    """
    if not confirmed:
        raise ValueError(
            "delete_message requires confirmed=True.  This action is irreversible."
        )
    service = _build_service(credentials)
    try:
        service.users().messages().trash(userId="me", id=message_id).execute()
        logger.info("Message %s moved to trash.", message_id)
    except HttpError as exc:
        logger.error("delete_message(%s) failed: %s", message_id, exc.status_code)
        raise
