"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True,  server_default=sa.text("gen_random_uuid()")),
        sa.Column("google_sub", sa.String(),  nullable=False),
        sa.Column("email",      sa.String(),  nullable=False),
        sa.Column("name",       sa.String(),  nullable=True),
        sa.Column("picture",    sa.String(),  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_seen",  sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("google_sub"),
    )

    op.create_table(
        "documents",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id",     UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename",    sa.String(),  nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=False),
        sa.Column("status",      sa.String(),  nullable=False, server_default=sa.text("'uploaded'")),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])

    op.create_table(
        "pages",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_num",    sa.Integer(), nullable=False),
        sa.Column("doc_type",    sa.String(),  nullable=True),
        sa.Column("title",       sa.String(),  nullable=True),
        sa.Column("sections",    JSONB(),      nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("validation",  JSONB(),      nullable=True),
        sa.Column("edited",      sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("document_id", "page_num"),
    )
    op.create_index("ix_pages_document_id", "pages", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_pages_document_id",     table_name="pages")
    op.drop_table("pages")
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("users")
