# Verification — 27 October 2026

## Verified source

Source commit `79606c691e9ec254c789ba4bb0bdb9ef377f927d` passed GitHub run https://github.com/unnyanr11/universal-chatbot/actions/runs/40500434504. This document is a subsequent documentation-only update; the linked run identifies the exact tested code.

| Check | Observed result |
|---|---|
| SQLite backend | 36 passed, 1 PostgreSQL-specific test skipped |
| PostgreSQL 17 backend | 37 passed |
| Chromium acceptance | All 6 Playwright journeys passed |
| Frontend and clients | React/TypeScript production build and reusable React component type check passed |
| Python hygiene | Ruff lint and format checks passed |
| Synthetic retrieval | All 3 evaluation cases passed |
| Actual local models | SmolLM2 135m and 360m completion/token streaming passed; authenticated API SSE path passed |
| Semantic ingestion | Actual all-minilm embeddings, durable worker indexing and semantic retrieval passed |
| Guided Docker installation | Fresh install and rerun passed with real models, generated database credentials, initial owner/assistant and starter-guide worker indexing |
| HTTPS configuration | Caddy configuration validation passed; public DNS/certificates are checked by the wizard on the destination server |

Backend checks cover tenant isolation, source deletion/redaction, publish/rollback pinning, tool boundaries, owned conversations, handoff privacy, workspace erasure, consent, membership/session controls, workflow dry-run/version/recovery and concurrent booking invariants. Calendar coverage includes shared staff capacity across services, policy invalidation of pending approval, DST ambiguity rejection and a PostgreSQL policy-edit/confirmation race. Request bounds cover declared and chunked payloads before parsing.

The six browser journeys exercise sourced chat and booking/cancellation; authenticated iframe chat; configuration publication and workflow simulation; human handoff/private notes and customer erasure; managed calendars and booking; and server-owned in-chat booking cards with cross-view booking refresh.

These are runtime checks, not answer-quality, production-capacity or security-certification claims. See BENCHMARKS.md for measured model smoke observations and their limits. The authoring environment could not run Chromium directly because downloaded archives were invalid; browser acceptance ran in CI. No screenshot or pixel-level visual review claim is made. The Expo example has no device/emulator acceptance and is not a shipped native app. Optional unimplemented adapters are listed in STATUS.md.

Dependency audit: Vite was upgraded to 7.3.7 after an initial high-severity development-server finding. Subsequent npm audit reported zero vulnerabilities in the locked JS dependency tree at that time. This does not cover Python packages, model weights or application logic. A broader security review, transitive licence inventory, model-answer quality study and production load testing remain outside these acceptance checks.

Known dependency warning: the pinned Starlette TestClient bridge reports its httpx integration deprecated in favour of httpx2. The bridge still passes the suite; migrate it before an upgrade removes compatibility.

## Guided installer acceptance

The source run above invoked `scripts/setup.py` in a fresh CI environment with actual model downloads and a password supplied over stdin. The installer built/started the full Compose stack, created the initial owner and assistant, completed real model/embedding checks and indexed the getting-started guide. A second invocation completed with existing accounts/database credentials preserved. The backend suite independently verifies login to the bootstrapped workspace, preservation of existing users, safe configuration persistence and explicit child-process stdin isolation.

All six browser journeys and both database suites passed on the same source commit. Public certificate issuance was not exercised against a real domain in CI: Caddy configuration validation passed, and the installer waits for verified public HTTPS on the operator's chosen domain before declaring a public deployment complete. No public host or DNS record was created in this work.

## Cloud-provider extension (pending source CI)

Completion/streaming adapters and private configuration support OpenAI, Gemini, Claude, Kimi, NVIDIA, DeepSeek and operator-approved compatible endpoints. Offline wire contracts and API/tenant/credential tests passed locally; no user cloud credentials were supplied, so no live cloud-account acceptance is claimed. A browser journey now saves each cloud preset and restores the default without paid requests. The updated source run will be recorded after CI completes.
