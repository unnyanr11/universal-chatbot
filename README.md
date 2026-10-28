# Universal Chatbot · Assistant Studio

A self-hostable, local-first assistant platform with a React admin application, document-grounded chat, published guest and authenticated website widgets, transactional appointments, human support and durable local workflows. No paid AI API is required. This is a local platform release; optional provider and enterprise features have explicit boundaries in [STATUS.md](docs/STATUS.md).

## Working capabilities

- Separate organisations/projects, assistants, roles, invitation links, expiring/revocable sessions and password rotation.
- Versioned assistant branding/configuration, draft/publish/source manifests, import/export and rollback.
- TXT/Markdown/CSV/DOCX/text-PDF ingestion with durable worker leases, bounded extraction and deletion/redaction.
- Lexical search, optional local semantic/hybrid retrieval, cited passage answers and provisional streaming with Ollama, OpenAI, Gemini, Claude, Kimi, NVIDIA, DeepSeek and approved compatible endpoints.
- Owned conversation history, short follow-up context, export/delete and server-created booking cards directly inside chat.
- Services/staff, opening periods/breaks, holidays, buffers, lead times, windows, cancellation policy and DST-safe availability.
- Explicit booking approval, atomic slot/staff capacity, idempotent receipts, cancellation and rescheduling rollback.
- Human inbox, agent assignment/replies, private notes and paused automation during handoff.
- Versioned visual workflow sequences, typed inputs, bounded branches, local tools, dry runs, checkpoints and recovery.
- Tool contracts/sandbox, explicit-consent expiring preference records, workspace data export/erasure, audit and measured analytics.
- Durable in-app reminders, typed JS/SSE client, reusable React component and a React Native source example.

Source-passage mode is a non-generative baseline: it quotes retrieved passages and does not pretend to be model inference. Generated text cannot create controls, manufacture tool results or execute actions.

## Ready-to-use setup (recommended)

Install **Docker with Compose v2**, **Git** and **Python 3.10+**. Start Docker, then run:

```bash
git clone https://github.com/unnyanr11/universal-chatbot.git
cd universal-chatbot
python3 scripts/setup.py
```

On Windows use `python scripts/setup.py`. Already cloned? Run `git pull` first, then the setup command.

The wizard asks for a domain (blank means localhost), an AI provider, your owner email, organisation and a password. Cloud providers also require a model ID and API key. It generates a private database password, builds the application, runs migrations, prepares the selected generation provider and local embedding model, creates your account and assistant, and indexes a product getting-started guide. It tests actual model completion, embeddings, the worker, database and UI before reporting success. Your account password is sent over stdin, never saved in `.env` or command arguments. Rerunning preserves existing accounts, database credentials and data; it resumes interrupted setup rather than resetting the installation.

Open the URL printed by setup and sign in with **your chosen owner email/password**. AI mode is selected automatically when the provider is available/configured. Ask **“How do I upload my business documents?”** to test the starter guide, then add your own approved documents in Knowledge. The guide describes this product; it does not supply fictional business policies, staff or availability. Add your real services and staff in Calendars before testing bookings.

The default local profile uses `smollm2:360m` and `all-minilm:latest`; it is a small CPU profile verified by runtime smoke tests, not a business-answer quality guarantee. Downloads and builds require internet, storage and time. To explicitly start without AI/model downloads, use `python3 scripts/setup.py --source-only` (source-passage answers). To use another installed/reviewed model, set its exact tag in the generated `.env` and rerun setup; the installer preserves nonempty model tags.

### Public HTTPS hosting

Run the same wizard **on your server** and enter a domain such as `chat.example.com`. Point the domain's DNS to that server first and permit inbound **TCP 80/443** (and UDP 443 if using HTTP/3). The installer starts Caddy with automatic HTTPS, keeps database/Ollama ports private, and waits for the public HTTPS health check. It reports a failure rather than claiming readiness when DNS, certificate issuance or routing fails. No domain is purchased or DNS changed automatically. Keep the server's firewall and DNS under your control.

For a local-only server test, keep the domain blank and connect from your computer with `ssh -L 8000:127.0.0.1:8000 user@server`, then visit `http://localhost:8000`.

For unattended setup, use `--domain`, `--owner-email`, `--organization`, `--password-stdin` and `--no-browser`; supply the password through a protected stdin source. Use `--port 8001` if localhost port 8000 is already occupied. Existing accounts are never silently reset. Keep `.env` private and back up the database before upgrading an existing installation.

## Native setup

For a single-domain Vercel deployment with separate FastAPI and Vite services plus
a private worker daemon, see [VERCEL.md](VERCEL.md). This requires an initialized
external PostgreSQL database and server-side secrets; the Docker wizard is separate.

Requires Python 3.12 and Node.js 22.12+ or 24. From the repository root:

```bash
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on Linux/macOS:

```bash
pip install -r requirements.txt
pip install --no-deps -e .
python -m platform_api.migrate
```

Choose **one** initial account path:

- **Synthetic demo:** set `DEMO_PASSWORD` to a unique random password of at least 16 characters, then run `python -m platform_api.seed`. PowerShell: `$env:DEMO_PASSWORD = "your-unique-random-password"`; Bash: `export DEMO_PASSWORD='your-unique-random-password'`.
- **Empty account database:** run `python -m platform_api.bootstrap` and enter the owner email, organisation and password interactively. It creates an assistant and queued getting-started guide. No demo accounts are added; existing accounts are preserved.

Build the UI and start the application:

```bash
cd apps/admin
npm ci
npm run build
cd ../..
uvicorn platform_api.app:create_app --factory --host 127.0.0.1 --port 8000 --limit-concurrency 64
```

In a second activated terminal, from the repository root:

```bash
python -m platform_api.worker
```

Open **http://127.0.0.1:8000**. The demo has `owner@cedar.example`, `agent@cedar.example`, `customer@cedar.example` and corresponding `harbor.example` accounts, using your chosen demo password. They are fictional businesses with separate data. The seed also creates draft assistants, services and fixed slots for the next two weeks; rerun it to refresh the window without changing existing passwords.

For development, `npm run dev` in `apps/admin` proxies `/v1` to the API. Production-built assets are served from the API origin. Without a build, `/` reports `FRONTEND_NOT_BUILT` while API documentation remains at `/docs`.

## Docker Compose

The Compose build/start path passed in GitHub CI; see [verification](docs/VERIFICATION.md).

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD in .env to a unique URL-safe random value.
docker compose up --build -d
docker compose run --rm -e DEMO_PASSWORD='your-unique-long-password' api python -m platform_api.seed
```

Alternatively bootstrap an empty database with `docker compose run --rm api python -m platform_api.bootstrap`. Compose runs PostgreSQL, migration, API, worker and Ollama. Only the application port is published to loopback; raw model and database ports are private. Native commands require exported shell variables; `.env` is automatically read by Compose only.

## Cloud API keys

Select OpenAI, Gemini, Claude, Kimi, NVIDIA, DeepSeek or a custom compatible service in the setup wizard, or configure an assistant in **Settings → AI provider**. Settings keys are encrypted and write-only. Owners/administrators can save, replace, test and remove credentials. Connection tests make small actual requests; provider charges apply according to your account. Cloud generation sends relevant questions/source/context text to that provider.

See [PROVIDERS.md](docs/PROVIDERS.md) for configuration, custom endpoint approval, secure key storage, error handling and explicit live-account testing limits. Embeddings remain local, or use lexical retrieval without embeddings. No cloud API key was supplied for live cloud-provider acceptance in this work; offline adapter contracts and browser configuration are tested separately.

## Enable local models

Models are optional and downloaded separately after hardware/licence review. The verified CPU smoke profile uses Apache-2.0 SmolLM2 configurations and all-minilm:

```bash
ollama pull smollm2:360m
ollama pull all-minilm:latest
```

Export `OLLAMA_MODEL=smollm2:360m` and `OLLAMA_EMBED_MODEL=all-minilm:latest` in both API and worker environments, then restart them. In Compose, set those entries in `.env`, pull weights with `docker compose exec ollama ollama pull <model-tag>`, then recreate API/worker services.

Choose Local model and semantic/hybrid retrieval in Chat. Embeddings apply to subsequent uploads; existing files must be re-uploaded after enabling them. Semantic indexing is bounded at 64 chunks/document, with a visible lexical-only warning above that budget. No index is reported ready when embeddings are unconfigured. `python -m platform_api.doctor` reports configuration/hardware availability.

The adapter limits active completions to one per API process, with 4,096 context tokens, 256 output tokens and a 65-second total deadline. Small smoke models prove runtime operation, not business-answer quality. [BENCHMARKS.md](docs/BENCHMARKS.md) records actual observations and hardware; they are not minimum requirements or public-throughput promises.

## Reproducible walkthrough

1. **Knowledge:** upload approved information and watch queued → ready/failed with the worker running. Ask a sourced question, inspect its citation and compare retrieval methods in the debugger.
2. **Settings:** save a draft and publish it. New sources stay outside the published manifest until republished. Restore a prior version; deleted sources do not reappear.
3. **Chat:** type “Book an appointment.” Choose an exact service/date/time in the server-created card, review its policy and explicitly confirm. Refreshing/replaying the card cannot create another booking. Cancellation/rescheduling also require confirmation.
4. **Calendars:** create staff and a managed service, edit policy and generate dates. Shared staff cannot be booked concurrently across services. Policy changes invalidate pending approvals; regenerate future availability afterward. Legacy demo slots remain a separate fixed-slot profile.
5. **Support:** request human help from Chat. In another session, an owner/agent claims the ticket, adds a private note and sends a human reply. Customer “Refresh replies” never exposes the private note. Return the ticket to the assistant to resume automation.
6. **Workflows:** save the provided booking template, run a labelled dry run, then a live version. Live runs stop at an exact approval preview. Saved runs remain pinned to their definition and resume after interruption.
7. **Privacy:** inspect/forget explicit preferences, view delivered in-app reminders, export owned data or erase workspace activity. Accounts/shared knowledge/backups remain; the UI states those limits.
8. **Integrate:** apply a starter template, review/import selected website pages, create a private draft preview, publish, enable public chat and copy the public loader. WordPress ZIP, shareable chat, signed identity, installation checks, diagnostics and approved signed webhooks are available. See [INTEGRATION.md](docs/INTEGRATION.md).

## Verification

```bash
ruff check .
ruff format --check .
pytest -q
python evaluation/run.py
python -m pip check
cd apps/admin
npm run build
npm run format:check
npx tsc -p ../../packages/react-sdk/tsconfig.json
npx playwright install chromium
npm run test:e2e
```

Browser tests start an isolated synthetic API/worker; stop any server occupying port 8000 first. CI also runs the backend suite on PostgreSQL, real local model/embedding smoke checks and the Compose stack. Consult [VERIFICATION.md](docs/VERIFICATION.md) for observed runs rather than assuming a newly added check passed.

## Documentation

- [Architecture and boundaries](docs/ARCHITECTURE.md)
- [Security, privacy and retention](docs/SECURITY.md)
- [Operations and backup/restore](docs/OPERATIONS.md)
- [AI providers and API keys](docs/PROVIDERS.md)
- [Guided onboarding, WordPress, identity, webhooks and safe updates](docs/INTEGRATION.md)
- [Client integrations](docs/CLIENTS.md)
- [Feature status](docs/STATUS.md)

No external email, SMS, commerce, payment, calendar or arbitrary HTTP connector is silently enabled. Those adapters require reviewed implementation and, where applicable, credentials. Voice, Flutter and enterprise SSO are optional future capabilities. The mobile source example still needs device/emulator acceptance. No production security certification, unlimited free inference, invented accuracy or business impact is claimed.
