# Verification — 27 October 2026

Observed locally for the knowledge/booking preview:

- Python 3.12 environment with pinned Python dependencies installed successfully.
- React/TypeScript production build passed (`tsc --noEmit && vite build`), including the modular screens and typed HTTP client.
- Python lint and formatting passed.
- 14 backend tests passed. They exercise real SQLite writes for tenant boundaries, sessions, roles, ingestion/worker execution, actual PDF extraction, source removal/redaction, SSE final events, job lease recovery, booking ownership, duplicate confirmations, competing last-slot commits, expiring confirmations and rescheduling rollback.
- Three synthetic lexical retrieval smoke cases passed. This is not model accuracy, multilingual validation or a portfolio performance benchmark.
- Full live Uvicorn/worker HTTP journey passed: compiled UI/loader delivery, login, upload, real worker extraction, cited chat, service/slot lookup, booking, idempotent confirmation retry, cancellation and source deletion. This verifies HTTP integration, not browser rendering.

Adapter transport tests use a clearly labelled HTTP double and do not count as real AI inference. Booking integration tests use the actual local booking tables and constraints, not mocked booking success.

Browser acceptance passed in GitHub CI after fixing the service selector’s accessible name. Both Playwright journeys passed: upload → ingestion → cited chat/source preview → booking → cancellation → source deletion, and authentication/chat through the actual iframe loader. Run: https://github.com/unnyanr11/universal-chatbot/actions/runs/40477348625 . Local Chromium downloads still returned invalid archives, so browser execution used the CI runner. No screenshot or pixel-level visual QA claim is made.

Not verified here: PostgreSQL migrations/concurrency, Docker build/Compose, actual Ollama model inference, target-user hardware latency, semantic retrieval, mobile integration, external delivery, security audit or complete transitive licence inventory. No adoption or business-impact metrics are claimed.

Dependency audit: the initial Vite pin had a reported high-severity development-server vulnerability. It was updated to 7.3.7; the subsequent npm audit reported zero vulnerabilities in this locked dependency tree. This audit does not cover Python packages, model weights or application-level security.

Known dependency warning: Starlette currently deprecates its httpx TestClient bridge in favour of httpx2. The pinned bridge still passes the suite; migrate before upgrading to a version that removes it.
