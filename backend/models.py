import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id         : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_sub : Mapped[str]              = mapped_column(String, unique=True, nullable=False)
    email      : Mapped[str]              = mapped_column(String, nullable=False)
    name       : Mapped[Optional[str]]    = mapped_column(String, nullable=True)
    picture    : Mapped[Optional[str]]    = mapped_column(String, nullable=True)
    created_at : Mapped[datetime]         = mapped_column(DateTime(timezone=True), default=_now)
    last_seen  : Mapped[datetime]         = mapped_column(DateTime(timezone=True), default=_now)

    documents: Mapped[list["Document"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename    : Mapped[str]           = mapped_column(String, nullable=False)
    total_pages : Mapped[int]           = mapped_column(Integer, nullable=False)
    status      : Mapped[str]           = mapped_column(String, nullable=False, default="uploaded")
    created_at  : Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)
    updated_at  : Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)

    user  : Mapped["User"]       = relationship(back_populates="documents")
    pages : Mapped[list["Page"]] = relationship(back_populates="document", cascade="all, delete-orphan", order_by="Page.page_num")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("document_id", "page_num"),)

    id          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_num    : Mapped[int]           = mapped_column(Integer, nullable=False)
    doc_type    : Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title       : Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sections    : Mapped[list]          = mapped_column(JSONB, nullable=False, default=list)
    validation  : Mapped[Optional[dict]]= mapped_column(JSONB, nullable=True)
    edited      : Mapped[bool]          = mapped_column(Boolean, nullable=False, default=False)
    created_at  : Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)
    updated_at  : Mapped[datetime]      = mapped_column(DateTime(timezone=True), default=_now)

    document: Mapped["Document"] = relationship(back_populates="pages")
