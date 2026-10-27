# Verification — 27 October 2026

## Verified source

Source commit `3df2ccd28b83a034a1c521f4708a858e79ee7108` passed GitHub run https://github.com/unnyanr11/universal-chatbot/actions/runs/40491072791. This document is a subsequent documentation-only update; the linked run identifies the exact tested code.

| Check | Observed result |
|---|---|
| SQLite backend | 33 passed, 1 PostgreSQL-specific test skipped |
| PostgreSQL 17 backend | 34 passed |
| Chromium acceptance | All 6 Playwright journeys passed |
| Frontend and clients | React/TypeScript production build and reusable React component type check passed |
| Python hygiene | Ruff lint and format checks passed |
| Synthetic retrieval | All 3 evaluation cases passed |
| Actual local models | SmolLM2 135m and 360m completion/token streaming passed; authenticated API SSE path passed |
| Semantic ingestion | Actual all-minilm embeddings, durable worker indexing and semantic retrieval passed |
| Docker Compose | Full image build/start, compiled UI delivery, health check and PostgreSQL seed passed |

Backend checks cover tenant isolation, source deletion/redaction, publish/rollback pinning, tool boundaries, owned conversations, handoff privacy, workspace erasure, consent, membership/session controls, workflow dry-run/version/recovery and concurrent booking invariants. Calendar coverage includes shared staff capacity across services, policy invalidation of pending approval, DST ambiguity rejection and a PostgreSQL policy-edit/confirmation race. Request bounds cover declared and chunked payloads before parsing.

The six browser journeys exercise sourced chat and booking/cancellation; authenticated iframe chat; configuration publication and workflow simulation; human handoff/private notes and customer erasure; managed calendars and booking; and server-owned in-chat booking cards with cross-view booking refresh.

These are runtime checks, not answer-quality, production-capacity or security-certification claims. See BENCHMARKS.md for measured model smoke observations and their limits. The authoring environment could not run Chromium directly because downloaded archives were invalid; browser acceptance ran in CI. No screenshot or pixel-level visual review claim is made. The Expo example has no device/emulator acceptance and is not a shipped native app. Optional unimplemented adapters are listed in STATUS.md.

Dependency audit: Vite was upgraded to 7.3.7 after an initial high-severity development-server finding. Subsequent npm audit reported zero vulnerabilities in the locked JS dependency tree at that time. This does not cover Python packages, model weights or application logic. A broader security review, transitive licence inventory, model-answer quality study and production load testing remain outside these acceptance checks.

Known dependency warning: the pinned Starlette TestClient bridge reports its httpx integration deprecated in favour of httpx2. The bridge still passes the suite; migrate it before an upgrade removes compatibility.
