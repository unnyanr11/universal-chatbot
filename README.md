# Universal AI Assistant Platform

A self-hostable assistant platform built in verified milestones. This release is a **partial Phase 0 foundation**, not a knowledge assistant or booking product yet.

## What runs today

- FastAPI application with generated OpenAPI documentation.
- PostgreSQL-compatible relational schema and an explicit, repeatable initial migration.
- Native SQLite development profile, verified here without Docker.
- Argon2 password hashing, opaque one-hour bearer sessions stored only as hashes, logout/revocation, and a durable login budget.
- Membership-derived project access; owner/administrator/developer may create draft assistants, read-only roles cannot.
- Two fictional businesses seeded explicitly with an operator-supplied password.
- Configurable Ollama adapter, health report and bounded diagnostic completion. Missing configuration produces an error, never fabricated AI output.
- Six database-backed/adapter tests and lint/format CI.

There is no admin UI, widget, knowledge ingestion, booking, worker, notification delivery, or external connector in this release. Use `/docs` to exercise the working API. See [feature status](docs/STATUS.md) before evaluating capabilities.

## Native setup (Python 3.12)

Run commands from this directory. PowerShell users should activate `.venv\Scripts\Activate.ps1` and set variables with `$env:NAME = 'value'`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install --no-deps -e .
python -m platform_api.migrate
export DEMO_PASSWORD='replace-with-your-own-long-random-password'
python -m platform_api.seed
python -m platform_api.doctor
uvicorn platform_api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Use `owner@cedar.example` or `owner@harbor.example` and the password you chose. No demo password is built into the source. Rerunning the seed preserves existing accounts; it does not rotate passwords. The local database contains password hashes and session records: exclude it from source control and protect disk access.

Open http://127.0.0.1:8000/docs. Create a session using `POST /v1/sessions`, copy `access_token` into Authorize, list projects, then list or create assistants under a returned project ID. Log out with `DELETE /v1/sessions/current` and verify access fails. Log in as the other business to verify the first project's ID returns 404. Lists currently cap at 100; cursor pagination is pending.

## Compose profile (provided, not verified in this environment)

Docker is not available in the build environment. Review and validate this profile locally before relying on it.

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD in .env to a unique URL-safe random string.
docker compose up --build -d
# Supply DEMO_PASSWORD explicitly; no seed runs automatically.
docker compose run --rm -e DEMO_PASSWORD='your-unique-long-password' api python -m platform_api.seed
```

The API binds to loopback. PostgreSQL and Ollama have no published ports. Migration runs before the API. Ollama uses a CPU-only persistent volume profile. For native inference, install Ollama separately; model weights are not bundled or downloaded automatically. `OLLAMA_MODEL` must match the full tag shown by `/api/tags`. In Compose, download an approved model with `docker compose exec ollama ollama pull <reviewed-model-tag>`, set `OLLAMA_MODEL`, and recreate the API.

No model was selected: deployment hardware, latency requirements and model licence approval are unknown. The diagnostic endpoint is ungrounded, does not execute tools and should not be exposed publicly. It caps input at 4,000 characters and generation at 256 tokens/2,048 context, with a 60-second HTTP timeout. Global inference admission control is pending.

## Checks

```bash
ruff check .
ruff format --check .
pytest -q
python -m pip check
```

See [verification](docs/VERIFICATION.md) for actual results and limits. Dependencies are pinned, including transitive dependencies, in `requirements.txt`. The lock currently includes development tools to keep this first slice simple; split production/development locks when packaging is hardened.

## Next milestones

1. Finish Phase 0: PostgreSQL acceptance, actual local-model smoke test, configuration guardrails, membership/session administration and inference limits.
2. Phase 1: React administration, text/PDF ingestion, retrieval, grounded answers/citations, durable ingestion worker and isolated streaming widget.
3. Phase 2: real local booking tools, confirmation records, concurrent-slot protection, idempotency and reminders.
4. Phases 3–7: reviewed connectors, SDKs/mobile, human support, workflow engine and measured evaluations.

Implement and verify each slice before marking it complete. Do not deploy this development foundation to a public network.
