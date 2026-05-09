"""init postgres state

Revision ID: 20260509_0001
Revises: 
Create Date: 2026-05-09 00:00:00
"""

import uuid

import bcrypt
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260509_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("clearance", sa.String(length=32), nullable=False),
        sa.Column("passwordHash", sa.String(length=255), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("userId", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tokenHash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("userId", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("chatId", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokenCount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "chat_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("chatId", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("extractedEntities", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "user_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("userId", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memoryKey", sa.String(length=255), nullable=False),
        sa.Column("memoryValue", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("userId", "memoryKey", name="uq_user_memory_user_key"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("userId", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entityType", sa.String(length=64), nullable=False),
        sa.Column("entityId", sa.String(length=128), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("ix_chats_user_updated", "chats", ["userId", "updatedAt"])
    op.create_index("ix_messages_chat_created", "messages", ["chatId", "createdAt"])
    op.create_index("ix_user_memory_user_updated", "user_memory", ["userId", "updatedAt"])
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["userId", "createdAt"])

    users_table = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("username", sa.String),
        sa.column("email", sa.String),
        sa.column("role", sa.String),
        sa.column("clearance", sa.String),
        sa.column("passwordHash", sa.String),
    )

    seed = [
        {
            "id": uuid.uuid4(),
            "username": "omar",
            "email": None,
            "role": "Admin",
            "clearance": "restricted",
            "passwordHash": bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        },
        {
            "id": uuid.uuid4(),
            "username": "sara",
            "email": None,
            "role": "Senior Compliance",
            "clearance": "confidential",
            "passwordHash": bcrypt.hashpw("compliance123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        },
        {
            "id": uuid.uuid4(),
            "username": "ahmed",
            "email": None,
            "role": "Compliance Analyst",
            "clearance": "internal",
            "passwordHash": bcrypt.hashpw("staff123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        },
        {
            "id": uuid.uuid4(),
            "username": "guest",
            "email": None,
            "role": "External",
            "clearance": "public",
            "passwordHash": bcrypt.hashpw("guest".encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        },
    ]
    op.bulk_insert(users_table, seed)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_index("ix_user_memory_user_updated", table_name="user_memory")
    op.drop_index("ix_messages_chat_created", table_name="messages")
    op.drop_index("ix_chats_user_updated", table_name="chats")

    op.drop_table("audit_logs")
    op.drop_table("user_memory")
    op.drop_table("chat_memory")
    op.drop_table("messages")
    op.drop_table("chats")
    op.drop_table("user_sessions")
    op.drop_table("users")
