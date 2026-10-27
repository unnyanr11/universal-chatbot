# Verification — 27 October 2026

## Observed baseline extension

GitHub run https://github.com/unnyanr11/universal-chatbot/actions/runs/40482903584 passed all three jobs:

- Python backend suite against SQLite and PostgreSQL 17, including tenant isolation, source deletion/redaction, publish/rollback pinning, tool boundaries, owned conversations, handoff privacy, workspace erasure, consent, membership/session controls, workflow dry-run/version/recovery and concurrent booking invariants.
- React/TypeScript production build, reusable React component type check, Python lint/format and synthetic retrieval evaluation.
- Four real Playwright browser journeys: sourced chat and booking/cancellation; authenticated iframe chat; configuration publication and workflow simulation; human handoff/private notes and customer workspace erasure.
- Actual Ollama completion and token streaming for two local model configurations, all-minilm embeddings, worker indexing and semantic retrieval. These are real runtime calls, separate from test doubles.
- Full Docker Compose build/start, compiled UI delivery and PostgreSQL seed using the built image.

See BENCHMARKS.md for the exact observed smoke measurements and their limits.

## Current calendar/tool hardening

The local suite additionally exercises shared staff capacity across different services, calendar-policy invalidation of pending approval, DST ambiguity rejection, schema-validated local tool calls, pre-parser/chunked request bounds and citation ordering. Its final source/test count and CI result will be recorded after the current commit is checked. Adding tests does not itself establish that they passed in every environment.

The frontend production build and source formatting are checked after each UI change. The authoring environment cannot run Chromium directly because downloaded archives were invalid; browser acceptance uses CI. The Expo example has no device/emulator acceptance and is not a shipped native app. No screenshot or pixel-level visual review claim is made.

Dependency audit: Vite was upgraded to 7.3.7 after an initial high-severity development-server finding. Subsequent npm audit reported zero vulnerabilities in the locked JS dependency tree at that time. This does not cover Python packages, model weights or application logic. A broader security review, transitive licence inventory, model-answer quality study and production load testing remain outside these acceptance checks.

Known dependency warning: the pinned Starlette TestClient bridge reports its httpx integration deprecated in favour of httpx2. The bridge still passes the suite; migrate it before an upgrade removes compatibility.
