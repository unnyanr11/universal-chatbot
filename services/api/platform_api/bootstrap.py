"""Explicit initial owner setup without development fixtures or embedded passwords."""

import getpass
import os

from sqlalchemy import select

from .app import passwords
from .database import Membership, Organization, Project, User, connect


def main():
    email = input("Owner email: ").strip().lower()
    name = input("Organisation name: ").strip()
    password = getpass.getpass("Password (at least 16 characters): ")
    if (
        email.count("@") != 1
        or any(c.isspace() for c in email)
        or len(email) > 254
        or not 1 <= len(name) <= 100
        or not 16 <= len(password) <= 256
    ):
        raise SystemExit("Valid email, organisation and password are required")
    engine, sessions = connect(os.getenv("DATABASE_URL", "sqlite:///./assistant.db"))
    with sessions.begin() as db:
        if db.scalar(select(User.id).limit(1)):
            raise SystemExit("Bootstrap is only available for an empty user database")
        user = User(email=email, password_hash=passwords.hash(password))
        org = Organization(name=name)
        db.add_all([user, org])
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
        db.add(Project(organization_id=org.id, name=name + " workspace"))
    engine.dispose()
    print("Initial owner and organisation created. No demo accounts were added.")


if __name__ == "__main__":
    main()
