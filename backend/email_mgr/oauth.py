"""
Gmail OAuth2 flow with Fernet-encrypted credential storage.

Security notes:
- Credentials are NEVER logged
- State parameter validated to prevent CSRF
- Tokens stored encrypted at rest using OAUTH_ENCRYPTION_KEY
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GMAIL_SCOPES_BASE = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
]

GMAIL_SCOPE_SEND = "https://www.googleapis.com/auth/gmail.send"
GMAIL_SCOPE_MODIFY = "https://www.googleapis.com/auth/gmail.modify"

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/email/oauth/callback")

_FERNET_KEY: Optional[bytes] = None


def _get_fernet() -> Fernet:
    """Return a Fernet cipher using the OAUTH_ENCRYPTION_KEY env var."""
    global _FERNET_KEY
    if _FERNET_KEY is None:
        raw = os.environ.get("OAUTH_ENCRYPTION_KEY", "")
        if not raw:
            raise RuntimeError("OAUTH_ENCRYPTION_KEY environment variable is not set.")
        # Accept raw 32-byte key or URL-safe base64-encoded Fernet key
        _FERNET_KEY = raw.encode() if raw.startswith("b'") is False else raw.encode()
    return Fernet(_FERNET_KEY)


# ---------------------------------------------------------------------------
# In-memory state store (replace with Redis/DB in production)
# ---------------------------------------------------------------------------
# Maps state -> {"user_id": str, "created_at": float}
_STATE_STORE: dict[str, dict] = {}

STATE_TTL_SECONDS = 600  # 10 minutes


def _store_state(state: str, user_id: str) -> None:
    _STATE_STORE[state] = {"user_id": user_id, "created_at": time.time()}


def _validate_and_consume_state(state: str) -> str:
    """
    Validate the CSRF state parameter.  Returns the associated user_id.
    Raises ValueError if state is unknown, already used, or expired.
    """
    entry = _STATE_STORE.pop(state, None)
    if entry is None:
        raise ValueError("Invalid or already-used OAuth state parameter.")
    age = time.time() - entry["created_at"]
    if age > STATE_TTL_SECONDS:
        raise ValueError("OAuth state parameter has expired.")
    return entry["user_id"]


def _purge_expired_states() -> None:
    """Remove expired state entries (call periodically)."""
    cutoff = time.time() - STATE_TTL_SECONDS
    expired = [k for k, v in _STATE_STORE.items() if v["created_at"] < cutoff]
    for k in expired:
        del _STATE_STORE[k]


# ---------------------------------------------------------------------------
# Credential encryption helpers
# ---------------------------------------------------------------------------

def _encrypt_credentials(credentials: Credentials) -> str:
    """Serialize and encrypt a Credentials object to a safe string."""
    data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }
    plaintext = json.dumps(data).encode()
    return _get_fernet().encrypt(plaintext).decode()


def _decrypt_credentials(encrypted: str) -> Credentials:
    """Decrypt and deserialise a Credentials object."""
    try:
        plaintext = _get_fernet().decrypt(encrypted.encode())
    except InvalidToken as exc:
        raise ValueError("Credential decryption failed – key mismatch or tampered data.") from exc

    data = json.loads(plaintext)
    import datetime
    expiry = datetime.datetime.fromisoformat(data["expiry"]) if data.get("expiry") else None
    return Credentials(
        token=data["token"],
        refresh_token=data["refresh_token"],
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"],
        expiry=expiry,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _build_flow(extra_scopes: list[str] | None = None) -> Flow:
    scopes = GMAIL_SCOPES_BASE.copy()
    if extra_scopes:
        for s in extra_scopes:
            if s not in scopes:
                scopes.append(s)

    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [GOOGLE_REDIRECT_URI],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(
        client_config=client_config,
        scopes=scopes,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )


def get_auth_url(
    user_id: str,
    state: Optional[str] = None,
    enable_send: bool = False,
    enable_modify: bool = False,
) -> str:
    """
    Generate a Google OAuth2 authorisation URL.

    Parameters
    ----------
    user_id:
        The platform user requesting access.
    state:
        Optional caller-supplied state; one will be generated if omitted.
    enable_send:
        Include gmail.send scope.
    enable_modify:
        Include gmail.modify scope (labels / archive).

    Returns
    -------
    str
        The URL the user should be redirected to.
    """
    _purge_expired_states()

    if state is None:
        state = secrets.token_urlsafe(32)

    _store_state(state, user_id)

    extra_scopes: list[str] = []
    if enable_send:
        extra_scopes.append(GMAIL_SCOPE_SEND)
    if enable_modify:
        extra_scopes.append(GMAIL_SCOPE_MODIFY)

    flow = _build_flow(extra_scopes)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    # NEVER log the URL – it contains the state token
    logger.info("OAuth URL generated for user_id=%s", hashlib.sha256(user_id.encode()).hexdigest()[:8])
    return auth_url


def exchange_code(code: str, state: str) -> tuple[Credentials, str]:
    """
    Validate *state*, exchange authorisation *code* for tokens.

    Returns
    -------
    (Credentials, user_id)
        Raw Google credentials plus the platform user_id extracted from state.
    """
    user_id = _validate_and_consume_state(state)  # raises on invalid/expired

    flow = _build_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Fetch the Gmail address so we can store it
    service = build("oauth2", "v2", credentials=credentials)
    user_info = service.userinfo().get().execute()
    email_address = user_info.get("email", "unknown")

    logger.info(
        "OAuth exchange successful user_id=%s email_hash=%s",
        hashlib.sha256(user_id.encode()).hexdigest()[:8],
        hashlib.sha256(email_address.encode()).hexdigest()[:8],
    )
    # Attach email as a hint for the caller (not sensitive – public address)
    credentials.email_address = email_address  # type: ignore[attr-defined]
    return credentials, user_id


def refresh_credentials(encrypted_credentials: str) -> tuple[Credentials, str]:
    """
    Refresh an expired access token.

    Parameters
    ----------
    encrypted_credentials:
        The encrypted credential string as stored in the DB.

    Returns
    -------
    (Credentials, encrypted_str)
        Refreshed credentials and the new encrypted string to persist.
    """
    import google.auth.transport.requests as grequests

    credentials = _decrypt_credentials(encrypted_credentials)
    request = grequests.Request()
    credentials.refresh(request)
    logger.info("Credentials refreshed successfully.")
    new_encrypted = _encrypt_credentials(credentials)
    return credentials, new_encrypted


def revoke_credentials(encrypted_credentials: str) -> None:
    """
    Revoke access token at Google's endpoint.

    Parameters
    ----------
    encrypted_credentials:
        The encrypted credential string as stored in the DB.
    """
    import requests as _requests

    credentials = _decrypt_credentials(encrypted_credentials)
    if credentials.token:
        resp = _requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": credentials.token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        if resp.status_code not in (200, 400):
            # 400 means already revoked – treat as success
            logger.warning("Revocation returned status %s", resp.status_code)
    logger.info("Credentials revoked.")


def get_credentials_from_encrypted(encrypted: str) -> Credentials:
    """Decrypt credentials from storage and auto-refresh if expired."""
    import datetime
    credentials = _decrypt_credentials(encrypted)
    if credentials.expiry and credentials.expiry <= datetime.datetime.utcnow():
        credentials, _ = refresh_credentials(encrypted)
    return credentials


def encrypt_credentials(credentials: Credentials) -> str:
    """Public wrapper around _encrypt_credentials."""
    return _encrypt_credentials(credentials)
