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
