# Universal Chatbot · Assistant Studio

A local-first assistant platform with a React administrative UI, approved-source search, evidence-based chat, an authenticated iframe widget and a real local appointment service. **Development preview: the full roadmap is not complete.** See [feature status](docs/STATUS.md) for exact boundaries.

No paid AI API is required. Source-passage mode retrieves and quotes actual document passages without pretending to be generative AI. Optional local-model answers use Ollama and require installed, reviewed model weights.

## Quick start

Requires Python 3.12 and Node.js 22.12+ or 24. Run from the repository root:

```bash
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` on Windows PowerShell, or `source .venv/bin/activate` on Linux/macOS. Then:

```bash
pip install -r requirements.txt
pip install --no-deps -e .
python -m platform_api.migrate
```

Set a unique seed password (at least 16 characters):

```powershell
# Windows PowerShell
$env:DEMO_PASSWORD = "replace-with-your-own-random-password"
```

```bash
# Linux/macOS
export DEMO_PASSWORD='replace-with-your-own-random-password'
```

```bash
python -m platform_api.seed
cd apps/admin
npm ci
npm run build
cd ../..
uvicorn platform_api.app:create_app --factory --host 127.0.0.1 --port 8000
```

In a second activated terminal, from the repository root:

```bash
python -m platform_api.worker
```

Open **http://127.0.0.1:8000**. Sign in with `owner@cedar.example` or `owner@harbor.example` and your chosen seed password. No default password is embedded. The seed creates separate fictional businesses, draft assistants, services and non-overlapping slots for the next two weeks. Rerun it to refresh the window; existing accounts/passwords are preserved.

For frontend development use `npm run dev` in `apps/admin` while API and worker run; Vite proxies `/v1` to port 8000. Production-built assets are served by FastAPI from one origin. Without a frontend build, the API remains available and `/` reports `FRONTEND_NOT_BUILT`.

## Try the working journey

1. **Knowledge:** upload a UTF-8 TXT/Markdown/CSV, DOCX or text PDF (2 MB limit). The durable worker extracts and indexes passages. Observe queued → ready or a visible failure.
2. **Chat:** ask a question matching the source. Source-passage mode returns retrieved passages and live citations. An unrelated question returns insufficient information. Optional local model mode fails clearly if Ollama is unavailable.
3. Select a citation to inspect its passage. **Retrieval debugger** shows lexical ranking scores, not confidence percentages.
4. **Appointments:** select a service and slot, inspect the exact date/time/timezone and policy, then confirm. The booking is a durable database write, not a simulated result.
5. Reschedule or cancel through a new explicit confirmation. Losing a replacement slot preserves the original booking. Repeated confirmation cannot create duplicate bookings.
6. **Integrate:** copy the iframe loader snippet, or open `/demo-embed.html` and supply the assistant ID. This is an authenticated preview: users sign in inside the frame. A dedicated widget origin is recommended for embedding in another application.
7. Remove a source. Future retrieval/citations reject it and stored answers citing it are redacted. Already-downloaded browser content and backups cannot be recalled.

## Local inference

Install Ollama separately and review the licence/hardware needs of a suitable model. No model is silently selected or downloaded. Configure the exact full model tag returned by Ollama:

```bash
# Export these variables using the syntax for your shell.
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=your-reviewed-model:tag
```

Restart the API and choose Local model in Chat. `python -m platform_api.doctor` reports hardware/tool availability. The adapter has one active completion per API process, a 65-second total deadline and bounded context/output. Local-model answers can still be incorrect; citations are references to retrieved evidence, not proof of factual correctness. Lexical retrieval is the implemented baseline; embeddings/hybrid search and true token streaming remain pending.

## Docker Compose

Docker is unavailable in the build environment, so this path is **provided but unverified**.

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD to a unique URL-safe random value in .env.
docker compose up --build -d
docker compose run --rm -e DEMO_PASSWORD='your-unique-long-password' api python -m platform_api.seed
```

The multi-stage build compiles React and packages the Python API. Compose runs PostgreSQL, a one-shot migration, API, durable worker and Ollama. Only the application port is bound to loopback; raw inference/database ports are not exposed. Install model weights explicitly with `docker compose exec ollama ollama pull <reviewed-tag>` if needed.

`.env` is read automatically by Compose. Native commands require environment variables exported in the shell; there is no implicit dotenv loader.

## Checks

```bash
ruff check .
ruff format --check .
pytest -q
python evaluation/run.py
python -m pip check
cd apps/admin
npm run build
npm run format:check
npx playwright install chromium
npm run test:e2e
```

The browser tests start an isolated synthetic API and worker. Do not run them while another server occupies port 8000. CI runs backend tests, frontend type/build checks and real-browser journeys. See [verification](docs/VERIFICATION.md) for actual observed results; tests that could not run are not marked passed.

## Repository map

- `services/api/platform_api`: API, policies, schema, worker and inference adapter.
- `apps/admin/src/screens`: React screens; `useStudio.ts`: state/network coordination.
- `apps/admin/public`: versioned preview widget loader and embed demonstration.
- `packages/js-sdk`: small typed HTTP client with abort support.
- `tests`: policy, ingestion, deletion, database concurrency and booking tests.
- `evaluation`: reproducible synthetic lexical baseline smoke cases.
- `infra`, `compose.yaml`, `.github/workflows`: startup/build/CI configuration.
- `docs`: architecture, threat model, retention, operations and feature ledger.

This preview is for synthetic local development. Public deployment, guest access, signed host identity, full model evaluation, staff/calendar administration, workflow automation, human support and external integrations require additional milestones. No real messages, payments or external appointments are sent.
