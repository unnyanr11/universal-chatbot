"""Explicit development-only fixtures; passwords come from the operator."""

import os

from sqlalchemy import select

from .app import passwords
from .database import Assistant, Membership, Organization, Project, User, connect


def seed():
    if os.getenv("APP_ENV", "development") != "development":
        raise SystemExit("Demo seeding is restricted to development")
    password = os.getenv("DEMO_PASSWORD", "")
    if len(password) < 16:
        raise SystemExit("Set DEMO_PASSWORD to a unique value of at least 16 characters")
    engine, sessions = connect(os.getenv("DATABASE_URL", "sqlite:///./assistant.db"))
    with sessions.begin() as db:
        for slug, name in [("cedar", "Cedar Repair Studio"), ("harbor", "Harbor Bike Care")]:
            email = f"owner@{slug}.example"
            if db.scalar(select(User).where(User.email == email)):
                continue
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
                    welcome_message="Welcome! This foundation has no knowledge or booking tools yet.",
                )
            )
    engine.dispose()
    print("Seeded synthetic development businesses. Existing accounts were preserved.")


if __name__ == "__main__":
    seed()
