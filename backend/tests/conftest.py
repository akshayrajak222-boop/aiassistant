"""
tests/conftest.py – Shared pytest fixtures for the AI Agent Platform test suite.

Fixtures provided:
    - async_client        : AsyncClient (httpx) wired to the FastAPI app
    - db_session          : Async SQLAlchemy session against an in-memory SQLite DB
    - mock_ai_provider    : MockAIProvider that returns deterministic responses
    - mock_gmail          : monkeypatched Gmail API returning canned email data
    - test_user           : factory function that creates a User row + auth token
    - mock_email_creds    : fake encrypted OAuth credentials for EmailAccount rows
    - mock_hermes         : monkeypatched Hermes/agent that returns fake SSE chunks
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Re-export the FastAPI app.  We import lazily so we can override settings
# before the app module pulls them in.
# ---------------------------------------------------------------------------

# Override settings BEFORE importing the app so the DB URL is patched.
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-not-for-production")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMmNoYXJzISE=")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")

from backend.database.models import (  # noqa: E402
    Base,
    Conversation,
    EmailAccount,
    EmailActionApproval,
    EmailProvider,
    MemoryEntry,
    MemoryEntryType,
    Message,
    MessageRole,
    User,
)

# ---------------------------------------------------------------------------
# Event-loop policy (pytest-asyncio ≥ 0.21 requires explicit mode)
# ---------------------------------------------------------------------------

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default asyncio event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# In-memory SQLite engine / session
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create a fresh in-memory SQLite engine for each test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional AsyncSession that is rolled back after each test."""
    factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI app + AsyncClient
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Async httpx client pointed at the FastAPI app.

    The DB dependency is overridden to use the test session so every
    request shares the same in-memory SQLite instance.
    """
    # Import app here to avoid circular deps with settings patch
    try:
        from main import app  # type: ignore[import]
        from backend.database.connection import get_db  # type: ignore[import]
    except ImportError:
        # Minimal stub app when full app is not yet wired
        from fastapi import FastAPI
        app = FastAPI()

        async def get_db():  # type: ignore[override]
            yield db_session

    async def _override_get_db():
        yield db_session

    try:
        app.dependency_overrides[get_db] = _override_get_db  # type: ignore[name-defined]
    except Exception:
        pass

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    try:
        app.dependency_overrides.clear()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Mock AI provider
# ---------------------------------------------------------------------------

class MockAIProvider:
    """Deterministic mock AI provider used in all tests."""

    name = "mock"
    _responses: list[str] = ["This is a mock AI response."]
    _stream_chunks: list[str] = ["This ", "is ", "a ", "mock ", "response."]

    def supports_tools(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return True

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> str:
        return self._responses[0]

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ):
        for chunk in self._stream_chunks:
            yield chunk

    async def embed(self, text: str) -> list[float]:
        # Return a deterministic 128-dim vector
        return [0.1] * 128


@pytest.fixture
def mock_ai_provider() -> MockAIProvider:
    """Return a MockAIProvider instance."""
    return MockAIProvider()


@pytest.fixture
def patched_ai_provider(mock_ai_provider: MockAIProvider):
    """Monkeypatch the provider factory to return MockAIProvider."""
    with patch("providers.factory.ProviderFactory.get_provider", return_value=mock_ai_provider):
        yield mock_ai_provider


# ---------------------------------------------------------------------------
# Mock Gmail API
# ---------------------------------------------------------------------------

FAKE_GMAIL_MESSAGE = {
    "id": "msg_abc123",
    "threadId": "thread_abc123",
    "labelIds": ["INBOX", "UNREAD"],
    "snippet": "Hello from test",
    "payload": {
        "headers": [
            {"name": "From", "value": "sender@example.com"},
            {"name": "To", "value": "test@example.com"},
            {"name": "Subject", "value": "Test Email Subject"},
            {"name": "Date", "value": "Fri, 16 Oct 2026 10:00:00 +0000"},
        ],
        "mimeType": "text/plain",
        "body": {"data": "SGVsbG8gZnJvbSB0ZXN0"},  # base64 "Hello from test"
    },
    "internalDate": "1729072800000",
}

FAKE_GMAIL_LIST_RESPONSE = {
    "messages": [
        {"id": "msg_abc123", "threadId": "thread_abc123"},
        {"id": "msg_def456", "threadId": "thread_def456"},
    ],
    "resultSizeEstimate": 2,
}


@pytest.fixture
def mock_gmail():
    """
    Return a mock Gmail service object with canned list/get/send/drafts responses.
    """
    gmail_svc = MagicMock()

    # messages().list().execute()
    gmail_svc.users.return_value.messages.return_value.list.return_value.execute.return_value = (
        FAKE_GMAIL_LIST_RESPONSE
    )

    # messages().get().execute()
    gmail_svc.users.return_value.messages.return_value.get.return_value.execute.return_value = (
        FAKE_GMAIL_MESSAGE
    )

    # messages().send().execute()
    gmail_svc.users.return_value.messages.return_value.send.return_value.execute.return_value = {
        "id": "sent_msg_001",
        "threadId": "thread_new",
        "labelIds": ["SENT"],
    }

    # drafts().create().execute()
    gmail_svc.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
        "id": "draft_001",
        "message": {"id": "draft_msg_001", "threadId": "thread_draft"},
    }

    return gmail_svc


@pytest.fixture
def patched_gmail(mock_gmail):
    """Monkeypatch build() so any Gmail service construction returns mock_gmail."""
    with patch("googleapiclient.discovery.build", return_value=mock_gmail):
        yield mock_gmail


# ---------------------------------------------------------------------------
# Test user factory
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    """
    Factory fixture: call it to create (user, raw_password, access_token) tuples.

    Usage::
        user, password, token = await test_user()
        user2, _, token2 = await test_user(email="other@example.com")
    """

    async def _create(
        email: str = "testuser@example.com",
        password: str = "S3cur3P@ssw0rd!",
        is_active: bool = True,
    ) -> tuple[User, str, str]:
        hashed = _pwd_ctx.hash(password)
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=hashed,
            is_active=is_active,
        )
        db_session.add(user)
        await db_session.flush()

        # Build a minimal JWT for this test user
        token = _make_test_token(user.id)
        return user, password, token

    return _create


def _make_test_token(user_id: str) -> str:
    """Create a test JWT without talking to the real auth service."""
    import time
    from jose import jwt

    secret = os.environ["JWT_SECRET_KEY"]
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_expired_token(user_id: str) -> str:
    """Create an already-expired JWT."""
    import time
    from jose import jwt

    secret = os.environ["JWT_SECRET_KEY"]
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": int(time.time()) - 7200,
        "exp": int(time.time()) - 3600,  # expired 1 hour ago
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# Expose helper for individual test modules
pytest.make_expired_token = _make_expired_token  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Mock email credentials
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_email_creds() -> bytes:
    """
    Return fake Fernet-encrypted OAuth credential bytes.
    Tests that need to create EmailAccount rows can use this as
    encrypted_credentials without actually calling Fernet.
    """
    # Raw credentials dict that would normally be encrypted
    fake_creds = {
        "token": "ya29.test-access-token",
        "refresh_token": "1//test-refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-google-client-id",
        "client_secret": "test-google-client-secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
    }
    # Return as raw bytes (tests mock the decrypt path as well)
    return json.dumps(fake_creds).encode()


@pytest_asyncio.fixture
async def connected_email_account(
    db_session: AsyncSession,
    test_user,
    mock_email_creds: bytes,
) -> EmailAccount:
    """Create a connected Gmail EmailAccount for the default test user."""
    user, _, _ = await test_user()
    account = EmailAccount(
        id=str(uuid.uuid4()),
        user_id=user.id,
        provider=EmailProvider.gmail,
        email_address="testuser@gmail.com",
        encrypted_credentials=mock_email_creds,
        scopes=["https://www.googleapis.com/auth/gmail.modify"],
        is_connected=True,
    )
    db_session.add(account)
    await db_session.flush()
    return account


# ---------------------------------------------------------------------------
# Mock Hermes agent
# ---------------------------------------------------------------------------

class MockHermesAgent:
    """
    Fake Hermes agent that yields deterministic SSE-style chunks.
    Monkeypatched into agent module during tests.
    """

    DEFAULT_CHUNKS = [
        "data: {\"type\": \"text\", \"content\": \"Here is your email summary: \"}\n\n",
        "data: {\"type\": \"text\", \"content\": \"You have 2 new messages.\"}\n\n",
        "data: {\"type\": \"done\", \"content\": \"\"}\n\n",
    ]

    def __init__(self, chunks: list[str] | None = None):
        self._chunks = chunks or self.DEFAULT_CHUNKS

    async def run_stream(self, *args: Any, **kwargs: Any):
        for chunk in self._chunks:
            yield chunk

    async def run(self, *args: Any, **kwargs: Any) -> str:
        return "".join(
            json.loads(c.replace("data: ", "").strip()).get("content", "")
            for c in self._chunks
            if c.startswith("data: ")
        )


@pytest.fixture
def mock_hermes():
    """Return a MockHermesAgent instance."""
    return MockHermesAgent()


@pytest.fixture
def patched_hermes(mock_hermes: MockHermesAgent):
    """
    Monkeypatch the Hermes agent class so agent.run_stream() is deterministic.
    """
    with patch("agent.hermes.HermesAgent", return_value=mock_hermes):
        with patch("agent.hermes.HermesAgent.run_stream", new=mock_hermes.run_stream):
            yield mock_hermes


# ---------------------------------------------------------------------------
# Auth header helper (re-exported for test modules)
# ---------------------------------------------------------------------------

def auth_headers(token: str) -> dict[str, str]:
    """Return an Authorization header dict for use with AsyncClient."""
    return {"Authorization": f"Bearer {token}"}


# Make it importable from conftest
pytest.auth_headers = auth_headers  # type: ignore[attr-defined]
