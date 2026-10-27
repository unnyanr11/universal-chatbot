"""Phase 0 API: opaque revocable sessions and membership-derived authorization."""

import os
import secrets
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .context import WRITERS, database, digest, identity, project_scope
from .database import Assistant, LoginWindow, Membership, Project, Session, User, connect
from .inference import OllamaProvider, ProviderUnavailable

passwords = PasswordHash.recommended()
dummy_hash = passwords.hash(secrets.token_urlsafe(32))


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class NewAssistant(Input):
    name: str = Field(min_length=1, max_length=100)
    welcome_message: str = Field(default="How can I help?", max_length=1000)


class Prompt(Input):
    text: str = Field(min_length=1, max_length=4000)


def create_app(database_url=None, provider=None):
    app = FastAPI(title="Universal Assistant Platform", version="0.3.0")
    from .limits import RequestBodyLimit

    app.add_middleware(RequestBodyLimit)
    engine, sessions = connect(
        database_url or os.getenv("DATABASE_URL", "sqlite:///./assistant.db")
    )
    app.state.engine = engine
    app.state.sessions = sessions
    app.state.provider = provider or OllamaProvider(
        os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), os.getenv("OLLAMA_MODEL", "")
    )

    @app.middleware("http")
    async def metadata(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path in {"/", "/demo-embed.html"}:
            ancestors = ["'self'"]
            if request.query_params.get("widget") and request.query_params.get("assistant"):
                import json

                from .database import AssistantSettings

                with sessions() as policy_db:
                    settings = policy_db.get(AssistantSettings, request.query_params["assistant"])
                    if settings:
                        for domain in json.loads(settings.configuration).get("allowed_domains", []):
                            scheme = (
                                "http"
                                if domain.split(":")[0] in {"localhost", "127.0.0.1"}
                                else "https"
                            )
                            ancestors.append(f"{scheme}://{domain}")
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
                "frame-ancestors " + " ".join(ancestors)
            )
        return response

    @app.exception_handler(HTTPException)
    async def api_error(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": str(exc.detail), "request_id": request.state.request_id}},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Do not echo submitted passwords or other raw inputs in validation errors.
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_INPUT",
                    "request_id": request.state.request_id,
                    "fields": [".".join(map(str, error["loc"])) for error in exc.errors()],
                }
            },
        )

    @app.get("/health")
    def health():
        return {"status": "alive", "milestone": "local-platform-preview"}

    @app.post("/v1/sessions", status_code=201)
    def login(body: Login, db=Depends(database)):
        # Global DB-backed minute budget also bounds arbitrary-identity guessing.
        key = f"login:{int(time.time()) // 60}"
        insert = sqlite_insert if engine.dialect.name == "sqlite" else pg_insert
        attempt = insert(LoginWindow).values(key=key, attempts=1)
        count = db.execute(
            attempt.on_conflict_do_update(
                index_elements=[LoginWindow.key], set_={"attempts": LoginWindow.attempts + 1}
            ).returning(LoginWindow.attempts)
        ).scalar_one()
        db.execute(
            delete(LoginWindow).where(LoginWindow.key < f"login:{int(time.time()) // 60 - 2}")
        )
        db.commit()
        if count > 20:
            raise HTTPException(429, "LOGIN_RATE_LIMITED", headers={"Retry-After": "60"})
        user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
        valid = passwords.verify(body.password, user.password_hash if user else dummy_hash)
        if not user or not valid:
            raise HTTPException(401, "INVALID_CREDENTIALS")
        token = secrets.token_urlsafe(32)
        session = Session(digest=digest(token), user_id=user.id)
        db.add(session)
        db.commit()
        return {"access_token": token, "token_type": "bearer", "expires_at": session.expires_at}

    @app.delete("/v1/sessions/current", status_code=204)
    def logout(session=Depends(identity), db=Depends(database)):
        db.delete(session)
        db.commit()

    @app.get("/v1/projects")
    def projects(session=Depends(identity), db=Depends(database)):
        rows = db.execute(
            select(Project, Membership.role)
            .join(Membership, Membership.organization_id == Project.organization_id)
            .where(Membership.user_id == session.user_id)
            .order_by(Project.id)
            .limit(100)
        )
        return {
            "items": [
                {
                    "id": p.id,
                    "name": p.name,
                    "environment": p.environment,
                    "organization_id": p.organization_id,
                    "role": role,
                }
                for p, role in rows
            ]
        }

    @app.get("/v1/projects/{project_id}/assistants")
    def assistants(scope=Depends(project_scope), db=Depends(database)):
        rows = db.scalars(
            select(Assistant)
            .where(Assistant.project_id == scope[0].id)
            .order_by(Assistant.id)
            .limit(100)
        )
        return {
            "items": [
                {
                    "id": a.id,
                    "name": a.name,
                    "status": a.status,
                    "welcome_message": a.welcome_message,
                    "version": a.version,
                }
                for a in rows
            ]
        }

    @app.post("/v1/projects/{project_id}/assistants", status_code=201)
    def create_assistant(body: NewAssistant, scope=Depends(project_scope), db=Depends(database)):
        if scope[1].role not in WRITERS:
            raise HTTPException(403, "ROLE_FORBIDDEN")
        assistant = Assistant(project_id=scope[0].id, **body.model_dump())
        db.add(assistant)
        db.commit()
        return {"id": assistant.id, "name": assistant.name, "status": assistant.status}

    @app.get("/v1/provider")
    async def provider_status(session=Depends(identity)):
        return await app.state.provider.check()

    @app.post("/v1/projects/{project_id}/inference-check")
    async def inference_check(body: Prompt, scope=Depends(project_scope)):
        if scope[1].role not in WRITERS:
            raise HTTPException(403, "ROLE_FORBIDDEN")
        try:
            answer = await app.state.provider.complete(body.text)
            return {"text": answer, "mode": "ungrounded-model-diagnostic"}
        except ProviderUnavailable:
            raise HTTPException(503, "LOCAL_INFERENCE_UNAVAILABLE") from None

    from .booking import router as booking_router
    from .calendars import router as calendar_router
    from .chat_actions import router as chat_action_router
    from .knowledge import router as knowledge_router
    from .management import router as management_router
    from .registry import router as registry_router
    from .support import router as support_router
    from .team import router as team_router
    from .workflows import router as workflow_router

    app.include_router(chat_action_router)
    app.include_router(registry_router)
    app.include_router(calendar_router)
    app.include_router(team_router)
    app.include_router(management_router)
    app.include_router(support_router)
    app.include_router(workflow_router)
    app.include_router(knowledge_router)
    app.include_router(booking_router)
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    web = Path(__file__).parent / "web"
    if (web / "index.html").exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    else:

        @app.get("/", include_in_schema=False)
        def frontend_not_built():
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "FRONTEND_NOT_BUILT",
                        "message": "Run npm ci and npm run build in apps/admin.",
                    }
                },
            )

    return app
