"""Explicit development-only fixtures; passwords come from the operator."""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .app import passwords
from .database import (
    Assistant,
    Membership,
    Organization,
    Project,
    Service,
    Slot,
    User,
    connect,
    environment_database_url,
)


def seed():
    if os.getenv("APP_ENV", "development") != "development":
        raise SystemExit("Demo seeding is restricted to development")
    password = os.getenv("DEMO_PASSWORD", "")
    if len(password) < 16:
        raise SystemExit("Set DEMO_PASSWORD to a unique value of at least 16 characters")
    engine, sessions = connect(environment_database_url())
    with sessions.begin() as db:
        for slug, name in [("cedar", "Cedar Repair Studio"), ("harbor", "Harbor Bike Care")]:
            email = f"owner@{slug}.example"
            existing = db.scalar(select(User).where(User.email == email))
            if existing:
                member = db.scalar(select(Membership).where(Membership.user_id == existing.id))
                project = db.scalar(
                    select(Project).where(Project.organization_id == member.organization_id)
                )
            else:
                user = User(email=email, password_hash=passwords.hash(password))
                org = Organization(name=name)
                db.add_all([user, org])
                db.flush()
                project = Project(organization_id=org.id, name=f"{name} demo")
                db.add(project)
                db.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
                db.flush()
                db.add(
                    Assistant(
                        project_id=project.id,
                        name=f"{name} assistant",
                        welcome_message="Welcome! Ask about our approved sources or browse appointments.",
                    )
                )
            for role, prefix in [("end_user", "customer"), ("support_agent", "agent")]:
                account_email = f"{prefix}@{slug}.example"
                if not db.scalar(select(User).where(User.email == account_email)):
                    account = User(email=account_email, password_hash=passwords.hash(password))
                    db.add(account)
                    db.flush()
                    db.add(
                        Membership(
                            user_id=account.id, organization_id=project.organization_id, role=role
                        )
                    )
            service = db.scalar(select(Service).where(Service.project_id == project.id))
            if not service:
                service = Service(
                    project_id=project.id,
                    name="Consultation" if slug == "cedar" else "Bike inspection",
                )
                db.add(service)
                db.flush()
            today = datetime.now(ZoneInfo(service.timezone)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            for day in range(1, 15):
                start = today + timedelta(days=day)
                if start.weekday() >= 5:
                    continue
                for hour in [9, 10, 11, 14, 15, 16]:
                    at = int(start.replace(hour=hour).timestamp())
                    if not db.scalar(
                        select(Slot.id).where(Slot.service_id == service.id, Slot.start_at == at)
                    ):
                        db.add(Slot(service_id=service.id, start_at=at, end_at=at + 1800))
    engine.dispose()
    print("Seeded synthetic development businesses. Existing accounts were preserved.")


if __name__ == "__main__":
    seed()
