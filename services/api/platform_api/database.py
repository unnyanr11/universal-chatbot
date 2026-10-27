"""Small relational schema shared by native SQLite and Compose PostgreSQL."""

import time
from uuid import uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def identifier():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str]


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    name: Mapped[str]


class Membership(Base):
    __tablename__ = "memberships"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    role: Mapped[str]


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("id", "organization_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str]
    environment: Mapped[str] = mapped_column(default="development")


class Assistant(Base):
    __tablename__ = "assistants"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str]
    welcome_message: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(default="draft")


class Session(Base):
    __tablename__ = "sessions"
    digest: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[int] = mapped_column(default=lambda: int(time.time()) + 3600)


class LoginWindow(Base):
    __tablename__ = "login_windows"
    key: Mapped[str] = mapped_column(primary_key=True)
    attempts: Mapped[int]


def connect(url):
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine, sessionmaker(engine, expire_on_commit=False)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("assistant_id", "content_hash"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), index=True)
    title: Mapped[str]
    content_hash: Mapped[str]
    content: Mapped[bytes]
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="queued")
    error: Mapped[str] = mapped_column(default="")
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    ordinal: Mapped[int]
    page: Mapped[int]
    text: Mapped[str]


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    state: Mapped[str] = mapped_column(default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    lease_until: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[str] = mapped_column(default="")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str]
    text: Mapped[str]
    # Citations resolve live; deleted source text is never copied into metadata.
    citation_ids: Mapped[str] = mapped_column(default="[]")
    created_at: Mapped[float] = mapped_column(default=time.time)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str]
    duration_minutes: Mapped[int] = mapped_column(default=30)
    timezone: Mapped[str] = mapped_column(default="Asia/Kolkata")
    location: Mapped[str] = mapped_column(default="Demo service desk")


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("service_id", "start_at"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), index=True)
    start_at: Mapped[int]
    end_at: Mapped[int]


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    slot_id: Mapped[str] = mapped_column(ForeignKey("slots.id"))
    status: Mapped[str] = mapped_column(default="confirmed")
    version: Mapped[int] = mapped_column(default=1)


class Reservation(Base):
    __tablename__ = "reservations"
    # Database uniqueness enforces last-slot capacity, across workers/processes.
    slot_id: Mapped[str] = mapped_column(ForeignKey("slots.id"), primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), unique=True)


class Operation(Base):
    __tablename__ = "operations"
    __table_args__ = (UniqueConstraint("user_id", "project_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str]
    kind: Mapped[str]
    slot_id: Mapped[str] = mapped_column(default="")
    booking_id: Mapped[str] = mapped_column(default="")
    booking_version: Mapped[int] = mapped_column(default=0)
    state: Mapped[str] = mapped_column(default="awaiting_confirmation")
    expires_at: Mapped[int] = mapped_column(default=lambda: int(time.time()) + 600)
    error: Mapped[str] = mapped_column(default="")


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("booking_id", "version"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), index=True)
    version: Mapped[int]
    due_at: Mapped[int]
    status: Mapped[str] = mapped_column(default="scheduled")
