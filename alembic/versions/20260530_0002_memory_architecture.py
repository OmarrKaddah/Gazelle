"""memory architecture v2 - message_citations, user_memory categories, chat_memory watermark

Revision ID: 20260530_0002
Revises: 20260509_0001
Create Date: 2026-05-30 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260530_0002"
down_revision = "20260509_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("messageId", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunkId", sa.Text(), nullable=False),
        sa.Column("docName", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_message_citations_message", "message_citations", ["messageId"])

    op.add_column("chat_memory", sa.Column("lastSummarizedMessageId", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("chat_memory", sa.Column("summaryTokens", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("user_memory", sa.Column("category", sa.String(length=32), nullable=False, server_default="preference"))
    op.add_column("user_memory", sa.Column("source", sa.String(length=16), nullable=False, server_default="explicit"))
    op.add_column("user_memory", sa.Column("evidenceChatId", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats.id", ondelete="SET NULL"), nullable=True))
    op.create_check_constraint(
        "user_memory_category_check", "user_memory",
        "category IN ('preference','instruction','profile','domain')",
    )
    op.create_check_constraint(
        "user_memory_source_check", "user_memory",
        "source IN ('explicit','promoted','inferred')",
    )
    op.drop_constraint("uq_user_memory_user_key", "user_memory", type_="unique")
    op.create_unique_constraint(
        "uq_user_memory_user_cat_key", "user_memory",
        ["userId", "category", "memoryKey"],
    )
    op.create_index("ix_user_memory_user_cat", "user_memory", ["userId", "category"])


def downgrade() -> None:
    op.drop_index("ix_user_memory_user_cat", table_name="user_memory")
    op.drop_constraint("uq_user_memory_user_cat_key", "user_memory", type_="unique")
    op.create_unique_constraint("uq_user_memory_user_key", "user_memory", ["userId", "memoryKey"])
    op.drop_constraint("user_memory_source_check", "user_memory", type_="check")
    op.drop_constraint("user_memory_category_check", "user_memory", type_="check")
    op.drop_column("user_memory", "evidenceChatId")
    op.drop_column("user_memory", "source")
    op.drop_column("user_memory", "category")

    op.drop_column("chat_memory", "summaryTokens")
    op.drop_column("chat_memory", "lastSummarizedMessageId")

    op.drop_index("ix_message_citations_message", table_name="message_citations")
    op.drop_table("message_citations")
