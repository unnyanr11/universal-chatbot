# Verification — 27 October 2026

## Verified source

Source commit `dd63dc85d9ae3ef001fd14962590f12bcc43847c` passed GitHub run https://github.com/unnyanr11/universal-chatbot/actions/runs/40503281046. This document is a subsequent documentation-only update; the linked run identifies the exact tested code.

| Check | Observed result |
|---|---|
| SQLite backend | 59 passed, 1 PostgreSQL-specific test skipped |
| PostgreSQL 17 backend | 60 passed |
| Chromium acceptance | All 7 Playwright journeys passed |
| Frontend and clients | React/TypeScript production build and reusable React component type check passed |
| Python hygiene | Ruff lint and format checks passed |
| Synthetic retrieval | All 3 evaluation cases passed |
| Actual local models | SmolLM2 135m and 360m completion/token streaming passed; authenticated API SSE path passed |
| Semantic ingestion | Actual all-minilm embeddings, durable worker indexing and semantic retrieval passed |
| Guided Docker installation | Fresh install and rerun passed with real models, generated database credentials, initial owner/assistant and starter-guide worker indexing |
| HTTPS configuration | Caddy configuration validation passed; public DNS/certificates are checked by the wizard on the destination server |

Backend checks cover tenant isolation, source deletion/redaction, publish/rollback pinning, tool boundaries, owned conversations, handoff privacy, workspace erasure, consent, membership/session controls, workflow dry-run/version/recovery and concurrent booking invariants. Calendar coverage includes shared staff capacity across services, policy invalidation of pending approval, DST ambiguity rejection and a PostgreSQL policy-edit/confirmation race. Request bounds cover declared and chunked payloads before parsing.

The first six browser journeys exercise sourced chat and booking/cancellation; authenticated iframe chat; configuration publication and workflow simulation; human handoff/private notes and customer erasure; managed calendars and booking; and server-owned in-chat booking cards with cross-view booking refresh.

These are runtime checks, not answer-quality, production-capacity or security-certification claims. See BENCHMARKS.md for measured model smoke observations and their limits. The authoring environment could not run Chromium directly because downloaded archives were invalid; browser acceptance ran in CI. No screenshot or pixel-level visual review claim is made. The Expo example has no device/emulator acceptance and is not a shipped native app. Optional unimplemented adapters are listed in STATUS.md.

Dependency audit: Vite was upgraded to 7.3.7 after an initial high-severity development-server finding. Subsequent npm audit reported zero vulnerabilities in the locked JS dependency tree at that time. This does not cover Python packages, model weights or application logic. A broader security review, transitive licence inventory, model-answer quality study and production load testing remain outside these acceptance checks.

Known dependency warning: the pinned Starlette TestClient bridge reports its httpx integration deprecated in favour of httpx2. The bridge still passes the suite; migrate it before an upgrade removes compatibility.

## Guided installer acceptance

The source run above invoked `scripts/setup.py` in a fresh CI environment with actual model downloads and a password supplied over stdin. The installer built/started the full Compose stack, created the initial owner and assistant, completed real model/embedding checks and indexed the getting-started guide. A second invocation completed with existing accounts/database credentials preserved. The backend suite independently verifies login to the bootstrapped workspace, preservation of existing users, safe configuration persistence and explicit child-process stdin isolation.

All seven browser journeys and both database suites passed on the same source commit. Public certificate issuance was not exercised against a real domain in CI: Caddy configuration validation passed, and the installer waits for verified public HTTPS on the operator's chosen domain before declaring a public deployment complete. No public host or DNS record was created in this work.

## Cloud-provider acceptance

The same verified source includes text completion/streaming adapters for OpenAI, Gemini, Claude, Kimi, NVIDIA, DeepSeek and operator-approved OpenAI-compatible endpoints. Offline HTTP wire contracts passed for every adapter, including native Claude events, hidden thinking deltas, sanitized authentication/rate-limit failures, no credential redirects/retries, truncated streams and immediate cancellation/admission release. API tests exercise encrypted assistant-bound write-only keys, cross-organisation access denial, owner/admin controls, revision conflicts, key preservation/replacement, lost-master-key failure and grounded regular/SSE chat through the saved provider.

The seventh Playwright journey saves all six cloud presets, verifies that responses and cleared input fields do not return the submitted key, and restores the deployment default. It makes no paid provider requests. The setup tests check master-key/database-password preservation and prevent a key from being silently reused after switching provider.

The Docker job passed real Ollama completion/streaming, authenticated application SSE, embeddings, first install, installer rerun and Caddy configuration validation with the new provider configuration. No cloud credentials were supplied, so live cloud-account/model acceptance remains unverified. `evaluation/cloud_smoke.py` provides explicit real completion/streaming checks for an operator's selected account; usage may be billed. See PROVIDERS.md for configuration, privacy and compatibility limits.

## Guided integration extension — awaiting source CI

The extension includes templates, reviewed website ingestion/styling, private draft preview, published guest chat, stable signed identity, enquiry capture, installation/diagnostic screens, a WordPress package, scoped signed webhook outbox, integration examples and backup/update/restore commands. Local existing backend and new boundary tests pass; expanded browser, real WordPress and backup/restore CI gates have been added. Their final observed source result will be recorded when the run completes. No external deployment, actual customer website import, paid cloud request or real webhook receiver contact is claimed.
