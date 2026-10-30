"""Verified Supabase Auth accounts mapped to isolated application workspaces."""

import os
import secrets
import time
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from .context import database, digest
from .database import (
    Assistant,
    LoginWindow,
    Membership,
    Organization,
    Project,
    PublicAccount,
    PublicWorkspace,
    Session,
    User,
)

router = APIRouter(prefix="/v1")


def auth_configuration():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not (parsed.hostname or "").endswith(".supabase.co")
        or parsed.path
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return None
    return (url, key) if key else None


def signup_enabled():
    return os.getenv("PUBLIC_SIGNUP_ENABLED", "false").lower() == "true" and bool(
        auth_configuration()
    )


def limit_registration(db):
    key = f"signup:{int(time.time()) // 60}"
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    attempt = insert(LoginWindow).values(key=key, attempts=1)
    count = db.execute(
        attempt.on_conflict_do_update(
            index_elements=[LoginWindow.key], set_={"attempts": LoginWindow.attempts + 1}
        ).returning(LoginWindow.attempts)
    ).scalar_one()
    db.execute(
        delete(LoginWindow).where(
            LoginWindow.key.like("signup:%"),
            LoginWindow.key < f"signup:{int(time.time()) // 60 - 2}",
        )
    )
    db.commit()
    if count > 10:
        raise HTTPException(429, "SIGNUP_RATE_LIMITED", headers={"Retry-After": "60"})


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=16, max_length=256)
    workspace_name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if value.count("@") != 1 or any(c.isspace() for c in value) or not all(value.split("@")):
            raise ValueError("Valid email required")
        return value

    @field_validator("workspace_name")
    @classmethod
    def name_valid(cls, value):
        if not value.strip():
            raise ValueError("Workspace name required")
        return value.strip()


async def auth_request(path, payload, *, method="POST", access_token=None):
    config = auth_configuration()
    if not config:
        raise HTTPException(503, "SIGNUP_UNAVAILABLE")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            headers = {"apikey": config[1]}
            if access_token:
                headers["Authorization"] = "Bearer " + access_token
            response = await client.request(
                method,
                config[0] + "/auth/v1/" + path,
                headers=headers,
                json=payload,
                params={"redirect_to": os.environ["PUBLIC_APP_URL"]}
                if path == "signup" and os.getenv("PUBLIC_APP_URL")
                else None,
            )
        result = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "AUTH_SERVICE_UNAVAILABLE") from None
    if not isinstance(result, dict):
        raise HTTPException(503, "AUTH_SERVICE_UNAVAILABLE")
    # Never forward upstream error bodies: they may contain submitted account data.
    if response.status_code == 429:
        raise HTTPException(429, "SIGNUP_RATE_LIMITED", headers={"Retry-After": "60"})
    if response.status_code >= 500:
        raise HTTPException(503, "AUTH_SERVICE_UNAVAILABLE")
    if response.is_error:
        code = (
            "EMAIL_CONFIRMATION_REQUIRED"
            if result.get("error_code") == "email_not_confirmed"
            else "INVALID_CREDENTIALS"
            if path.startswith("token")
            else "SIGNUP_FAILED"
        )
        raise HTTPException(400 if path == "signup" else 401, code)
    return result


@router.get("/registration")
def registration_status():
    return {"enabled": signup_enabled(), "email_confirmation": True, "own_api_key": True}


@router.post("/registrations", status_code=202)
async def register(body: Registration, db=Depends(database)):
    if not signup_enabled():
        raise HTTPException(403, "SIGNUP_DISABLED")
    limit_registration(db)
    await auth_request(
        "signup",
        {
            "email": body.email,
            "password": body.password,
            "data": {"workspace_name": body.workspace_name},
        },
    )
    return {"status": "check_email"}


async def login_public(db, email, password):
    if not auth_configuration():
        raise HTTPException(401, "INVALID_CREDENTIALS")
    result = await auth_request("token?grant_type=password", {"email": email, "password": password})
    remote = result.get("user") or {}
    # Only a successful server-to-server password exchange is trusted, never a client JWT.
    if not remote.get("email_confirmed_at") or remote.get("email", "").lower() != email:
        raise HTTPException(401, "EMAIL_CONFIRMATION_REQUIRED")
    try:
        subject = str(UUID(remote["id"]))
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, "AUTH_SERVICE_UNAVAILABLE") from None
    account = db.scalar(select(PublicAccount).where(PublicAccount.subject == subject))
    if not account:
        if not signup_enabled():
            raise HTTPException(403, "SIGNUP_DISABLED")
        # An Auth account cannot take over an existing local/bootstrap account by email.
        if db.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(409, "EXISTING_ACCOUNT_SIGN_IN_REQUIRED")
        from .app import passwords

        metadata = remote.get("user_metadata") or {}
        name = str(metadata.get("workspace_name", "My workspace")).strip()[:100] or "My workspace"
        user = User(email=email, password_hash=passwords.hash(secrets.token_urlsafe(32)))
        organization = Organization(name=name)
        db.add_all([user, organization])
        try:
            db.flush()
            account = PublicAccount(user_id=user.id, subject=subject)
            db.add_all(
                [
                    account,
                    PublicWorkspace(organization_id=organization.id),
                    Membership(user_id=user.id, organization_id=organization.id, role="owner"),
                ]
            )
            project = Project(organization_id=organization.id, name=name + " workspace")
            db.add(project)
            db.flush()
            db.add(
                Assistant(
                    project_id=project.id, name="My assistant", welcome_message="How can I help?"
                )
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            account = db.scalar(select(PublicAccount).where(PublicAccount.subject == subject))
            if not account:
                raise HTTPException(409, "EXISTING_ACCOUNT_SIGN_IN_REQUIRED") from None
    token = secrets.token_urlsafe(32)
    session = Session(digest=digest(token), user_id=account.user_id)
    db.add(session)
    db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": session.expires_at,
        "public_account": True,
    }
