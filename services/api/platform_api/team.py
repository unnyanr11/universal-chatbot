"""Local invitation links and membership administration. No email is sent."""

import secrets
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from .app import passwords
from .context import database, digest, identity, project_scope
from .database import (
    AuditEvent,
    Invitation,
    Membership,
    Operation,
    Organization,
    Project,
    Session,
    SupportTicket,
    User,
    WorkflowRun,
)

router = APIRouter(prefix="/v1")
ROLES = {"owner", "administrator", "developer", "support_agent", "analyst", "end_user"}


class InviteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254)
    role: str = "end_user"

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if value.count("@") != 1 or any(c.isspace() for c in value):
            raise ValueError("Invalid email")
        return value.lower()

    @field_validator("role")
    @classmethod
    def valid_role(cls, value):
        if value not in ROLES:
            raise ValueError("Unsupported role")
        return value


class InviteToken(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=100)


class JoinInput(InviteToken):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=16, max_length=256)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=16, max_length=256)


def admin(scope):
    if scope[1].role not in {"owner", "administrator"}:
        raise HTTPException(403, "TEAM_ADMIN_REQUIRED")


def consume(db, token, email):
    invitation = db.get(Invitation, digest(token))
    if not invitation or invitation.email != email.lower() or invitation.expires_at <= time.time():
        raise HTTPException(404, "INVITATION_INVALID_OR_EXPIRED")
    used = db.execute(
        update(Invitation)
        .where(Invitation.digest == invitation.digest, Invitation.consumed.is_(False))
        .values(consumed=True)
        .returning(Invitation.digest)
    ).scalar_one_or_none()
    if not used:
        raise HTTPException(409, "INVITATION_ALREADY_USED")
    return invitation


@router.get("/projects/{project_id}/members")
def members(scope=Depends(project_scope), db=Depends(database)):
    admin(scope)
    return {
        "items": [
            {"user_id": u.id, "email": u.email, "role": m.role}
            for m, u in db.execute(
                select(Membership, User)
                .join(User)
                .where(Membership.organization_id == scope[0].organization_id)
            )
        ]
    }


@router.post("/projects/{project_id}/invitations", status_code=201)
def invite(
    body: InviteInput, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    admin(scope)
    if scope[1].role != "owner" and body.role in {"owner", "administrator"}:
        raise HTTPException(403, "OWNER_REQUIRED_FOR_PRIVILEGED_ROLE")
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        digest=digest(token),
        organization_id=scope[0].organization_id,
        email=body.email,
        role=body.role,
        expires_at=int(time.time()) + 86400,
    )
    db.add(invitation)
    db.add(
        AuditEvent(
            project_id=scope[0].id,
            actor_id=session.user_id,
            kind="invitation_created",
            object_id="invitation",
        )
    )
    db.commit()
    return {
        "token": token,
        "expires_at": invitation.expires_at,
        "delivery": "Local link only. No email or message has been sent.",
    }


@router.post("/invitations/register", status_code=201)
def register(body: JoinInput, db=Depends(database)):
    if db.scalar(select(User.id).where(User.email == body.email.lower())):
        raise HTTPException(409, "SIGN_IN_TO_ACCEPT_EXISTING_ACCOUNT")
    invitation = consume(db, body.token, body.email)
    user = User(email=body.email.lower(), password_hash=passwords.hash(body.password))
    db.add(user)
    try:
        db.flush()
        db.add(
            Membership(
                user_id=user.id, organization_id=invitation.organization_id, role=invitation.role
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "ACCOUNT_OR_MEMBERSHIP_ALREADY_EXISTS") from None
    return {"status": "joined"}


@router.post("/invitations/accept")
def accept(body: InviteToken, session=Depends(identity), db=Depends(database)):
    user = db.get(User, session.user_id)
    invitation = consume(db, body.token, user.email)
    existing = db.get(Membership, (user.id, invitation.organization_id))
    if existing:
        raise HTTPException(409, "ALREADY_A_MEMBER")
    db.add(
        Membership(
            user_id=user.id, organization_id=invitation.organization_id, role=invitation.role
        )
    )
    db.commit()
    return {"status": "joined"}


@router.delete("/projects/{project_id}/members/{user_id}", status_code=204)
def remove_member(
    user_id: str, scope=Depends(project_scope), session=Depends(identity), db=Depends(database)
):
    admin(scope)
    # Serialize owner-count checks across project routes within the organisation.
    db.execute(
        update(Organization)
        .where(Organization.id == scope[0].organization_id)
        .values(name=Organization.name)
    )
    member = db.get(Membership, (user_id, scope[0].organization_id))
    if not member:
        raise HTTPException(404, "MEMBERSHIP_NOT_FOUND")
    if member.role in {"owner", "administrator"} and scope[1].role != "owner":
        raise HTTPException(403, "OWNER_REQUIRED_FOR_PRIVILEGED_ROLE")
    if (
        member.role == "owner"
        and db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.organization_id == member.organization_id, Membership.role == "owner")
        )
        <= 1
    ):
        raise HTTPException(409, "CANNOT_REMOVE_LAST_OWNER")
    projects = select(Project.id).where(Project.organization_id == member.organization_id)
    db.execute(
        update(Operation)
        .where(
            Operation.project_id.in_(projects),
            Operation.user_id == user_id,
            Operation.state == "awaiting_confirmation",
        )
        .values(state="cancelled")
    )
    db.execute(
        update(WorkflowRun)
        .where(
            WorkflowRun.project_id.in_(projects),
            WorkflowRun.user_id == user_id,
            WorkflowRun.state.in_(["waiting", "awaiting_confirmation"]),
        )
        .values(state="cancelled")
    )
    db.execute(
        update(SupportTicket)
        .where(
            SupportTicket.project_id.in_(projects),
            SupportTicket.assigned_to == user_id,
            SupportTicket.state == "assigned",
        )
        .values(assigned_to="", state="open", version=SupportTicket.version + 1)
    )
    db.execute(delete(Session).where(Session.user_id == user_id))
    db.delete(member)
    db.add(
        AuditEvent(
            project_id=scope[0].id,
            actor_id=session.user_id,
            kind="membership_removed",
            object_id=user_id,
        )
    )
    db.commit()


@router.post("/me/password", status_code=204)
def rotate_password(body: PasswordChange, session=Depends(identity), db=Depends(database)):
    user = db.get(User, session.user_id)
    if not passwords.verify(body.current_password, user.password_hash):
        raise HTTPException(401, "CURRENT_PASSWORD_INCORRECT")
    user.password_hash = passwords.hash(body.new_password)
    db.execute(delete(Session).where(Session.user_id == user.id))
    db.commit()
