"""
database/migrations/versions/001_initial.py – Creates all tables.

Revision ID: 001
Revises: (none)
Create Date: 2026-01-01 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision metadata ─────────────────────────────────────────────────────────
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ─────────────────────────────────────────────────────────────────
    message_role_enum = postgresql.ENUM(
        "user", "assistant", "system", "tool", name="message_role_enum", create_type=False
    )
    memory_entry_type_enum = postgresql.ENUM(
        "preference", "fact", "summary", "task",
        name="memory_entry_type_enum", create_type=False
    )
    email_provider_enum = postgresql.ENUM(
        "gmail", "outlook", name="email_provider_enum", create_type=False
    )
    email_action_type_enum = postgresql.ENUM(
        "send", "delete", "archive", "move",
        name="email_action_type_enum", create_type=False
    )
    approval_status_enum = postgresql.ENUM(
        "pending", "approved", "rejected", "executed",
        name="approval_status_enum", create_type=False
    )
    task_execution_status_enum = postgresql.ENUM(
        "pending", "running", "completed", "failed", "cancelled",
        name="task_execution_status_enum", create_type=False
    )

    for enum_type in [
        message_role_enum, memory_entry_type_enum, email_provider_enum,
        email_action_type_enum, approval_status_enum, task_execution_status_enum,
    ]:
        enum_type.create(op.get_bind(), checkfirst=True)

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── user_settings ─────────────────────────────────────────────────────────
    op.create_table(
        "user_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("assistant_name", sa.String(100), nullable=False, server_default="Aria"),
        sa.Column("system_instructions", sa.Text()),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("response_style", sa.String(50), nullable=False, server_default="balanced"),
        sa.Column("voice_id", sa.String(100)),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("default_model", sa.String(100)),
        sa.Column("ai_provider", sa.String(50), nullable=False, server_default="anthropic"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"])

    # ── conversations ─────────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "title", sa.String(255), nullable=False, server_default="New Conversation"
        ),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # ── messages ──────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", message_role_enum, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", postgresql.JSON()),
        sa.Column("token_count", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    # ── attachment_meta ───────────────────────────────────────────────────────
    op.create_table(
        "attachment_meta",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_attachment_meta_message_id", "attachment_meta", ["message_id"])

    # ── memory_entries ────────────────────────────────────────────────────────
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_type", memory_entry_type_enum, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSON()),
        sa.Column(
            "source_conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_memory_entries_user_id", "memory_entries", ["user_id"])

    # ── email_accounts ────────────────────────────────────────────────────────
    op.create_table(
        "email_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", email_provider_enum, nullable=False),
        sa.Column("email_address", sa.String(320), nullable=False),
        sa.Column("encrypted_credentials", sa.LargeBinary()),
        sa.Column("scopes", postgresql.JSON()),
        sa.Column("is_connected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "email_address", name="uq_email_account_user_address"),
    )
    op.create_index("ix_email_accounts_user_id", "email_accounts", ["user_id"])

    # ── email_action_approvals ────────────────────────────────────────────────
    op.create_table(
        "email_action_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", email_action_type_enum, nullable=False),
        sa.Column("email_data", postgresql.JSON(), nullable=False),
        sa.Column(
            "status",
            approval_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_email_action_approvals_user_id", "email_action_approvals", ["user_id"])

    # ── scheduled_tasks ───────────────────────────────────────────────────────
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("config", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_failures", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_scheduled_tasks_user_id", "scheduled_tasks", ["user_id"])

    # ── task_executions ───────────────────────────────────────────────────────
    op.create_table(
        "task_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("scheduled_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            task_execution_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result", postgresql.JSON()),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index("ix_task_executions_task_id", "task_executions", ["task_id"])

    # ── provider_usage ────────────────────────────────────────────────────────
    op.create_table(
        "provider_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_estimate", sa.Float()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_provider_usage_user_id", "provider_usage", ["user_id"])
    op.create_index("ix_provider_usage_created_at", "provider_usage", ["created_at"])

    # ── audit_events ──────────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", sa.String(255)),
        sa.Column("details", postgresql.JSON()),
        sa.Column("ip_address", sa.String(45)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("provider_usage")
    op.drop_table("task_executions")
    op.drop_table("scheduled_tasks")
    op.drop_table("email_action_approvals")
    op.drop_table("email_accounts")
    op.drop_table("memory_entries")
    op.drop_table("attachment_meta")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("user_settings")
    op.drop_table("users")

    for enum_name in [
        "message_role_enum",
        "memory_entry_type_enum",
        "email_provider_enum",
        "email_action_type_enum",
        "approval_status_enum",
        "task_execution_status_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
