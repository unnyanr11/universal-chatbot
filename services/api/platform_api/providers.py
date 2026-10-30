"""Tenant-scoped provider settings; write-only encrypted secrets never enter assistant exports."""

import json
import os

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

from .cloud import PRESETS, CloudProvider, endpoint
from .context import assistant_scope, database, identity
from .database import Assistant, AssistantProvider, Project, PublicWorkspace
from .inference import OllamaProvider, ProviderUnavailable

router = APIRouter(prefix="/v1")


def cipher():
    try:
        return Fernet(os.environ["PROVIDER_SECRET_KEY"].encode())
    except (KeyError, ValueError):
        raise ProviderUnavailable(code="PROVIDER_SECRET_KEY_UNAVAILABLE") from None


def seal(assistant_id, key):
    return (
        cipher().encrypt(json.dumps({"assistant_id": assistant_id, "key": key}).encode()).decode()
    )


def open_secret(context, encrypted):
    try:
        payload = json.loads(cipher().decrypt(encrypted.encode()))
        if payload["assistant_id"] != context:
            raise ValueError("Credential scope mismatch")
        return payload["key"]
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise ProviderUnavailable(code="PROVIDER_SECRET_KEY_UNAVAILABLE") from None


def unseal(row):
    return open_secret(row.assistant_id, row.encrypted_key)


def resolve_provider(request, db, assistant_id):
    row = db.get(AssistantProvider, assistant_id)
    if not row:
        return default_provider(request, db, assistant_id)
    if row.provider == "ollama":
        provider = OllamaProvider(os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), row.model)
        provider._gate = request.app.state.inference_gate
        return provider
    try:
        return CloudProvider(
            row.provider,
            row.model,
            unseal(row),
            row.base_url,
            row.max_tokens,
            row.token_parameter,
            gate=request.app.state.inference_gate,
        )
    except ValueError:
        raise ProviderUnavailable(code="PROVIDER_ENDPOINT_UNAVAILABLE") from None


def requires_own_key(db, assistant_id):
    assistant = db.get(Assistant, assistant_id)
    project = db.get(Project, assistant.project_id) if assistant else None
    return bool(project and db.get(PublicWorkspace, project.organization_id))


def default_provider(request, db, assistant_id):
    # Public tenants must never spend the operator's deployment key or local model.
    return (
        OllamaProvider("", "") if requires_own_key(db, assistant_id) else request.app.state.provider
    )


def metadata(request, row, db, assistant_id):
    default = default_provider(request, db, assistant_id)
    return {
        "provider": row.provider if row else getattr(default, "name", "ollama"),
        "model": row.model if row else getattr(default, "model", ""),
        "base_url": row.base_url if row else getattr(default, "base_url", ""),
        "max_tokens": row.max_tokens if row else getattr(default, "max_tokens", 1024),
        "token_parameter": row.token_parameter
        if row
        else getattr(default, "token_parameter", "max_tokens"),
        "has_key": bool(row.encrypted_key) if row else bool(getattr(default, "api_key", "")),
        "revision": row.revision if row else 0,
        "inherited": row is None,
        "requires_own_key": requires_own_key(db, assistant_id),
    }


def manager(scope):
    if scope[1].role not in {"owner", "administrator"}:
        raise HTTPException(403, "PROVIDER_ADMIN_REQUIRED")


class ProviderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    provider: str = Field(pattern="^(ollama|openai|gemini|claude|kimi|nvidia|deepseek|custom)$")
    model: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$")
    base_url: str = Field(default="", max_length=500)
    api_key: SecretStr | None = Field(default=None)
    max_tokens: int = Field(default=1024, ge=256, le=8192)
    token_parameter: str = Field(
        default="max_tokens", pattern="^(max_tokens|max_completion_tokens)$"
    )
    allow_external: bool = False


@router.get("/providers")
def catalog(session=Depends(identity)):
    return {
        "items": [{"id": "ollama", "name": "Local Ollama", "base_url": ""}]
        + [{"id": key, "name": name, "base_url": base} for key, (name, base) in PRESETS.items()]
        + [{"id": "custom", "name": "Custom OpenAI-compatible", "base_url": ""}],
        "custom_endpoints": [
            url.strip().rstrip("/")
            for url in os.getenv("AI_CUSTOM_BASE_URLS", "").split(",")
            if url.strip()
        ],
    }


@router.get("/assistants/{assistant_id}/provider")
def configuration(request: Request, scope=Depends(assistant_scope), db=Depends(database)):
    return {
        **metadata(request, db.get(AssistantProvider, scope[0].id), db, scope[0].id),
        "can_manage": scope[1].role in {"owner", "administrator"},
    }


@router.get("/assistants/{assistant_id}/provider/status")
async def status(request: Request, scope=Depends(assistant_scope), db=Depends(database)):
    try:
        return await resolve_provider(request, db, scope[0].id).check()
    except ProviderUnavailable as exc:
        return {"status": "unavailable", "reason": exc.code}


@router.put("/assistants/{assistant_id}/provider")
def save(
    body: ProviderInput, request: Request, scope=Depends(assistant_scope), db=Depends(database)
):
    manager(scope)
    assistant_id = scope[0].id
    if requires_own_key(db, assistant_id) and body.provider == "ollama":
        raise HTTPException(403, "OWN_AI_KEY_REQUIRED")
    row = db.get(AssistantProvider, assistant_id)
    if body.revision != (row.revision if row else 0):
        raise HTTPException(409, "PROVIDER_REVISION_CHANGED")
    values = {
        "provider": body.provider,
        "model": body.model,
        "max_tokens": body.max_tokens,
        "token_parameter": body.token_parameter,
        "revision": body.revision + 1,
    }
    if body.provider == "ollama":
        values.update(base_url="", encrypted_key="")
    else:
        if not body.allow_external:
            raise HTTPException(422, "EXTERNAL_PROVIDER_CONSENT_REQUIRED")
        try:
            values["base_url"] = endpoint(body.provider, body.base_url)
        except ValueError:
            raise HTTPException(422, "PROVIDER_ENDPOINT_NOT_APPROVED") from None
        secret = body.api_key.get_secret_value() if body.api_key else ""
        if secret:
            if (
                not 8 <= len(secret) <= 4096
                or not secret.isascii()
                or not secret.isprintable()
                or any(c.isspace() for c in secret)
            ):
                raise HTTPException(422, "PROVIDER_KEY_INVALID")
            try:
                values["encrypted_key"] = seal(assistant_id, secret)
            except ProviderUnavailable as exc:
                raise HTTPException(503, exc.code) from None
        elif (
            row
            and row.provider == body.provider
            and row.base_url == values["base_url"]
            and row.encrypted_key
        ):
            values["encrypted_key"] = row.encrypted_key
        else:
            raise HTTPException(422, "PROVIDER_KEY_REQUIRED")
    try:
        if row:
            changed = db.execute(
                update(AssistantProvider)
                .where(
                    AssistantProvider.assistant_id == assistant_id,
                    AssistantProvider.revision == body.revision,
                )
                .values(**values)
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "PROVIDER_REVISION_CHANGED")
        else:
            db.add(AssistantProvider(assistant_id=assistant_id, **values))
        from .management import audit

        audit(db, scope[0].project_id, scope[1].user_id, "provider_configured", assistant_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "PROVIDER_REVISION_CHANGED") from None
    db.expire_all()
    return metadata(request, db.get(AssistantProvider, assistant_id), db, assistant_id)


@router.delete("/assistants/{assistant_id}/provider", status_code=204)
def reset(revision: int, scope=Depends(assistant_scope), db=Depends(database)):
    manager(scope)
    result = db.execute(
        delete(AssistantProvider).where(
            AssistantProvider.assistant_id == scope[0].id, AssistantProvider.revision == revision
        )
    )
    if result.rowcount != 1:
        raise HTTPException(409, "PROVIDER_REVISION_CHANGED")
    from .management import audit

    audit(db, scope[0].project_id, scope[1].user_id, "provider_reset", scope[0].id)
    db.commit()


@router.post("/assistants/{assistant_id}/provider/test")
async def test(request: Request, scope=Depends(assistant_scope), db=Depends(database)):
    manager(scope)
    try:
        provider = resolve_provider(request, db, scope[0].id)
        db.rollback()
        answer = await provider.complete("Reply with the single word Ready.")
        if not answer.strip():
            raise ProviderUnavailable(code="PROVIDER_RESPONSE_INVALID")
        return {"status": "available"}
    except ProviderUnavailable as exc:
        raise HTTPException(503, exc.code) from None
