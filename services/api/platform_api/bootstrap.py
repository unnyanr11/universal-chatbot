"""Create the first owner and a usable workspace without demo identities."""

import argparse
import getpass
import hashlib
import json
import os
import sys

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select, text

from .app import passwords
from .database import Assistant, Document, Job, Membership, Organization, Project, User, connect

STARTER_TEXT = """# Getting started with Assistant Studio
Upload your approved business documents in Knowledge. Wait for each document to become ready
before asking questions about it. You can inspect the source citation beside an answer.
Use Settings to change your assistant's name, welcome message and suggested questions.
Publish the configuration after adding your own documents to pin the approved source set.
Use Calendars to add real staff, services and availability before accepting appointments.
Every booking requires a reviewed preview and explicit confirmation.
Invite colleagues from Team. Human support tickets are managed from Support.
This getting-started guide contains product instructions, not your business's policies.
You can delete it from Knowledge when you have added your own information.
"""


class InitialOwner(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=16, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if value.count("@") != 1 or any(c.isspace() for c in value) or value.startswith("@"):
            raise ValueError("Valid email required")
        if not value.split("@", 1)[1]:
            raise ValueError("Valid email required")
        return value

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Organisation name required")
        return value


def initialize(sessions, owner):
    with sessions.begin() as db:
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(1430340432, 2)"))
        if db.scalar(select(User.id).limit(1)):
            return {"created": False}
        user = User(email=owner.email, password_hash=passwords.hash(owner.password))
        org = Organization(name=owner.name)
        db.add_all([user, org])
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
        project = Project(organization_id=org.id, name=owner.name + " workspace")
        db.add(project)
        db.flush()
        assistant = Assistant(
            project_id=project.id,
            name="My assistant",
            welcome_message="Welcome! Ask how to get started, or upload your business information.",
        )
        db.add(assistant)
        db.flush()
        content = STARTER_TEXT.encode()
        document = Document(
            assistant_id=assistant.id,
            title="Getting started",
            kind="md",
            content=content,
            content_hash=hashlib.sha256(content).hexdigest(),
        )
        db.add(document)
        db.flush()
        db.add(Job(document_id=document.id))
        return {"created": True, "document_id": document.id}


def initialize_from_environment(sessions):
    """Optional first-owner setup for deployments without an interactive shell."""
    email = os.getenv("BOOTSTRAP_OWNER_EMAIL", "")
    password = os.getenv("BOOTSTRAP_OWNER_PASSWORD", "")
    if not email and not password:
        return {"created": False}
    try:
        owner = InitialOwner(
            email=email,
            password=password,
            name=os.getenv("BOOTSTRAP_ORGANIZATION", "My workspace"),
        )
    except ValidationError:
        # Pydantic exceptions contain submitted values, including the password.
        raise RuntimeError(
            "Set BOOTSTRAP_OWNER_EMAIL and a 16–256 character BOOTSTRAP_OWNER_PASSWORD; "
            "BOOTSTRAP_ORGANIZATION must be 1–100 characters."
        ) from None
    return initialize(sessions, owner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdin", action="store_true", help="Read owner JSON from stdin")
    parser.add_argument("--status", action="store_true", help="Report whether users exist")
    args = parser.parse_args()
    engine, sessions = connect(os.getenv("DATABASE_URL", "sqlite:///./assistant.db"))
    try:
        with sessions() as db:
            initialized = bool(db.scalar(select(User.id).limit(1)))
            document_id = db.scalar(
                select(Document.id)
                .where(Document.content_hash == hashlib.sha256(STARTER_TEXT.encode()).hexdigest())
                .limit(1)
            )
        if args.status:
            print(json.dumps({"initialized": initialized, "document_id": document_id}))
            return
        if initialized:
            print(json.dumps({"created": False}))
            return
        try:
            data = (
                json.loads(sys.stdin.read(8192))
                if args.stdin
                else {
                    "email": input("Owner email: "),
                    "name": input("Organisation name: "),
                    "password": getpass.getpass("Password (at least 16 characters): "),
                }
            )
            owner = InitialOwner.model_validate(data)
        except (ValueError, TypeError):
            # ValidationError includes input values; never print submitted credentials.
            raise SystemExit(
                "Valid email, organisation and 16–256 character password required"
            ) from None
        print(json.dumps(initialize(sessions, owner)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
