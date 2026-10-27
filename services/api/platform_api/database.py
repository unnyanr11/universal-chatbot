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
    content: Mapped[bytes] = mapped_column(deferred=True)
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


class AssistantVersion(Base):
    __tablename__ = "assistant_versions"
    __table_args__ = (UniqueConstraint("assistant_id", "number"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), index=True)
    number: Mapped[int]
    configuration: Mapped[str]
    published_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class AssistantSettings(Base):
    __tablename__ = "assistant_settings"
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), primary_key=True)
    configuration: Mapped[str] = mapped_column(default="{}")
    revision: Mapped[int] = mapped_column(default=1)
    published_version: Mapped[int] = mapped_column(default=0)


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str]
    state: Mapped[str] = mapped_column(default="open")
    assigned_to: Mapped[str] = mapped_column(default="")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class SupportNote(Base):
    __tablename__ = "support_notes"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    author_id: Mapped[str]
    text: Mapped[str]
    created_at: Mapped[float] = mapped_column(default=time.time)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    actor_id: Mapped[str]
    kind: Mapped[str]
    object_id: Mapped[str]
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class UserMemory(Base):
    __tablename__ = "user_memories"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str]
    expires_at: Mapped[int]
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str]
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (UniqueConstraint("workflow_id", "number"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id"), index=True)
    number: Mapped[int]
    definition: Mapped[str]


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (UniqueConstraint("project_id", "user_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    workflow_version_id: Mapped[str] = mapped_column(ForeignKey("workflow_versions.id"))
    idempotency_key: Mapped[str]
    state: Mapped[str] = mapped_column(default="waiting")
    cursor: Mapped[int] = mapped_column(default=0)
    variables: Mapped[str] = mapped_column(default="{}")
    trace: Mapped[str] = mapped_column(default="[]")
    revision: Mapped[int] = mapped_column(default=1)
    dry_run: Mapped[bool] = mapped_column(default=True)
    lease_until: Mapped[int] = mapped_column(default=0)


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (UniqueConstraint("chunk_id", "model"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"), index=True)
    model: Mapped[str]
    vector: Mapped[str]


class Invitation(Base):
    __tablename__ = "invitations"
    digest: Mapped[str] = mapped_column(primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str]
    role: Mapped[str]
    expires_at: Mapped[int]
    consumed: Mapped[bool] = mapped_column(default=False)


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str]


class ServicePolicy(Base):
    __tablename__ = "service_policies"
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), primary_key=True)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id"))
    configuration: Mapped[str]
    revision: Mapped[int] = mapped_column(default=1)


class SlotResource(Base):
    __tablename__ = "slot_resources"
    slot_id: Mapped[str] = mapped_column(ForeignKey("slots.id"), primary_key=True)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id"), index=True)
    policy_revision: Mapped[int]


class ResourceReservation(Base):
    __tablename__ = "resource_reservations"
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), primary_key=True)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id"), index=True)
    start_at: Mapped[int]
    end_at: Mapped[int]


class OperationPolicy(Base):
    __tablename__ = "operation_policies"
    operation_id: Mapped[str] = mapped_column(ForeignKey("operations.id"), primary_key=True)
    revision: Mapped[int]
    preview: Mapped[str]


class ChatAction(Base):
    __tablename__ = "chat_actions"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), unique=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str]
    operation_id: Mapped[str] = mapped_column(default="")


class AssistantProvider(Base):
    __tablename__ = "assistant_providers"
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), primary_key=True)
    provider: Mapped[str]
    model: Mapped[str]
    base_url: Mapped[str]
    encrypted_key: Mapped[str] = mapped_column(default="")
    max_tokens: Mapped[int] = mapped_column(default=1024)
    token_parameter: Mapped[str] = mapped_column(default="max_tokens")
    revision: Mapped[int] = mapped_column(default=1)


class AssistantIntegration(Base):
    __tablename__ = "assistant_integrations"
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    lead_capture: Mapped[bool] = mapped_column(default=False)
    support_enabled: Mapped[bool] = mapped_column(default=False)
    bookings_enabled: Mapped[bool] = mapped_column(default=False)
    daily_limit: Mapped[int] = mapped_column(default=100)
    revision: Mapped[int] = mapped_column(default=1)
    identity_secret: Mapped[str] = mapped_column(default="")


class WidgetSession(Base):
    __tablename__ = "widget_sessions"
    digest: Mapped[str] = mapped_column(
        ForeignKey("sessions.digest", ondelete="CASCADE"), primary_key=True
    )
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), index=True)
    revision: Mapped[int]
    verified: Mapped[bool] = mapped_column(default=False)
    preview: Mapped[bool] = mapped_column(default=False)


class VisitorIdentity(Base):
    __tablename__ = "visitor_identities"
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), primary_key=True)
    subject_digest: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


class IdentityNonce(Base):
    __tablename__ = "identity_nonces"
    digest: Mapped[str] = mapped_column(primary_key=True)
    expires_at: Mapped[int]


class IntegrationCounter(Base):
    __tablename__ = "integration_counters"
    key: Mapped[str] = mapped_column(primary_key=True)
    total: Mapped[int] = mapped_column(default=1)
    expires_at: Mapped[int] = mapped_column(default=lambda: int(time.time()) + 172800)


class WebsiteReview(Base):
    __tablename__ = "website_reviews"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), index=True)
    actor_id: Mapped[str]
    url: Mapped[str]
    title: Mapped[str]
    text: Mapped[str]
    color: Mapped[str]
    font_family: Mapped[str]
    expires_at: Mapped[int]


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    assistant_id: Mapped[str] = mapped_column(ForeignKey("assistants.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str]
    email: Mapped[str]
    message: Mapped[str]
    created_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    url: Mapped[str]
    secret: Mapped[str]
    enabled: Mapped[bool] = mapped_column(default=True)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("webhook_endpoints.id"), index=True)
    event: Mapped[str]
    payload: Mapped[str]
    state: Mapped[str] = mapped_column(default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    due_at: Mapped[int] = mapped_column(default=lambda: int(time.time()))
    lease_until: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[str] = mapped_column(default="")
    error: Mapped[str] = mapped_column(default="")
