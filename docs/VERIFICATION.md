# Verification — 27 October 2026

## Verified source

Source commit `3f976d228d0ba3a041633065792faefc69bcad1d` passed GitHub run https://github.com/unnyanr11/universal-chatbot/actions/runs/40514822888. This document is a subsequent documentation-only update; the linked run identifies the exact tested code.

| Check | Observed result |
|---|---|
| SQLite backend | 73 passed, 1 PostgreSQL-specific test skipped |
| PostgreSQL 17 backend | 74 passed |
| Browser acceptance | All 8 Playwright journeys passed |
| Frontend and clients | React/TypeScript production build and reusable React component type check passed |
| Python hygiene | Ruff lint and format checks passed |
| Synthetic retrieval | All 3 evaluation cases passed |
| Actual local models | SmolLM2 135m and 360m completion/token streaming passed; authenticated API SSE path passed |
| Semantic ingestion | Actual all-minilm embeddings, durable worker indexing and semantic retrieval passed |
| Guided Docker installation | Fresh install and rerun passed with real models, generated database credentials, initial owner/assistant and starter-guide worker indexing |
| WordPress/MySQL | Real activation, settings validation, rendered public widget attributes and deactivation passed |
| Backup/restore | PostgreSQL archive, archive validation and restore into an empty separate database passed |
| HTTPS configuration | Caddy configuration validation passed; public DNS/certificates are checked by the wizard on the destination server |

Backend checks cover tenant isolation, source deletion/redaction, publish/rollback pinning, tool boundaries, owned conversations, handoff privacy, workspace erasure, consent, membership/session controls, workflow dry-run/version/recovery and concurrent booking invariants. Calendar coverage includes shared staff capacity across services, policy invalidation of pending approval, DST ambiguity rejection and a PostgreSQL policy-edit/confirmation race. Request bounds cover declared and chunked payloads before parsing.

The first six browser journeys exercise sourced chat and booking/cancellation; authenticated iframe chat; configuration publication and workflow simulation; human handoff/private notes and customer erasure; managed calendars and booking; and server-owned in-chat booking cards with cross-view booking refresh.

These are runtime checks, not answer-quality, production-capacity or security-certification claims. See BENCHMARKS.md for measured model smoke observations and their limits. The authoring environment could not run Chromium directly because downloaded archives were invalid; browser acceptance ran in CI. No screenshot or pixel-level visual review claim is made. The Expo example has no device/emulator acceptance and is not a shipped native app. Optional unimplemented adapters are listed in STATUS.md.

Dependency audit: Vite was upgraded to 7.3.7 after an initial high-severity development-server finding. Subsequent npm audit reported zero vulnerabilities in the locked JS dependency tree at that time. This does not cover Python packages, model weights or application logic. A broader security review, transitive licence inventory, model-answer quality study and production load testing remain outside these acceptance checks.

Known dependency warning: the pinned Starlette TestClient bridge reports its httpx integration deprecated in favour of httpx2. The bridge still passes the suite; migrate it before an upgrade removes compatibility.

## Guided installer acceptance

The source run above invoked `scripts/setup.py` in a fresh CI environment with actual model downloads and a password supplied over stdin. The installer built/started the full Compose stack, created the initial owner and assistant, completed real model/embedding checks and indexed the getting-started guide. A second invocation completed with existing accounts/database credentials preserved. The backend suite independently verifies login to the bootstrapped workspace, preservation of existing users, safe configuration persistence and explicit child-process stdin isolation.

All eight browser journeys and both database suites passed on the same source commit. Public certificate issuance was not exercised against a real domain in CI: Caddy configuration validation passed, and the installer waits for verified public HTTPS on the operator's chosen domain before declaring a public deployment complete. No public host or DNS record was created in this work.

## Cloud-provider acceptance

The same verified source includes text completion/streaming adapters for OpenAI, Gemini, Claude, Kimi, NVIDIA, DeepSeek and operator-approved OpenAI-compatible endpoints. Offline HTTP wire contracts passed for every adapter, including native Claude events, hidden thinking deltas, sanitized authentication/rate-limit failures, no credential redirects/retries, truncated streams and immediate cancellation/admission release. API tests exercise encrypted assistant-bound write-only keys, cross-organisation access denial, owner/admin controls, revision conflicts, key preservation/replacement, lost-master-key failure and grounded regular/SSE chat through the saved provider.

The seventh Playwright journey saves all six cloud presets, verifies that responses and cleared input fields do not return the submitted key, and restores the deployment default. It makes no paid provider requests. The setup tests check master-key/database-password preservation and prevent a key from being silently reused after switching provider.

The Docker job passed real Ollama completion/streaming, authenticated application SSE, embeddings, first install, installer rerun and Caddy configuration validation with the new provider configuration. No cloud credentials were supplied, so live cloud-account/model acceptance remains unverified. `evaluation/cloud_smoke.py` provides explicit real completion/streaming checks for an operator's selected account; usage may be billed. See PROVIDERS.md for configuration, privacy and compatibility limits.

## Guided integration acceptance

The verified source includes templates, explicit website text review/import and colour/font suggestions, isolated private draft previews, published guest chat, stable signed host identity, optional enquiry/support/verified-booking controls, public UTC-day attempt limits, installation/diagnostic screens, a WordPress ZIP, approved signed webhook outbox, client examples and guarded backup/update/restore commands.

The eighth real browser journey exercised a published guest iframe without login, sourced chat/citations, consented enquiry submission, template changes, private preview of unpublished material and continued exclusion of that material from a new public session. The backend suite additionally checked route/tenant/ownership isolation, request limits, assertion expiry/replay, reviewed import and DNS exclusions, signature verification/retry with stable event IDs, disabled optional features and migration from schema revision eight with new features disabled. The current schema revision is nine.

A separate CI job ran real WordPress/PHP/MySQL, installed and activated the plugin, validated settings sanitization, fetched frontend HTML containing the correctly scoped public widget, then deactivated it and verified removal. The Docker job passed fresh setup/rerun and a pg_dump/pg_restore round trip into a separately created empty database. Archive readability and restored owner-row count were checked; no existing database was overwritten. The destructive update/rollback of a real production deployment was not executed.

Website-fetch boundary tests and external webhook delivery tests use explicit test doubles. No private/customer website, real receiver or paid cloud account was contacted during authoring. The static installation checker does not claim runtime browser/CSP verification. Public domain DNS/certificates, production load, native mobile and independent security/compliance acceptance remain deployment-specific checks. INTEGRATION.md documents those limits and the actual launch path.
