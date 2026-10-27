# Feature ledger

No phase is declared complete while its acceptance gates remain missing.

| Capability | Status | Working path / limitation |
|---|---|---|
| Relational schema and numbered additive migrations | Implemented, SQLite verified | v1 → v2 upgrade; PostgreSQL code path unverified |
| Authentication, token expiry/logout, login budget | Implemented | Argon2, hashed opaque sessions; global budget can be exhausted by another user |
| Tenant/project access and write roles | Implemented for existing routes | Membership checked on every protected route; invitations/member UI pending |
| Two synthetic businesses | Implemented | Explicit dev seed, separate assistants/services/schedules |
| React admin | Implemented preview | Overview, Knowledge, Chat, Appointments, Tools, Integrate; browser journeys passed in GitHub CI |
| Draft assistant creation | Partial | Create when project has no assistant; API can create additional drafts; publishing/history/config UI pending |
| TXT/Markdown/CSV/DOCX/text-PDF ingestion | Implemented | 2 MB upload; bounded subprocess extraction; DOCX has logical page 1; no OCR |
| Durable ingestion | Implemented | Atomic job claim, lease, bounded attempts, visible failure; transient DB outage may require process restart |
| Retrieval | Implemented baseline | Tenant-scoped lexical ranking; embeddings/hybrid/reranker not implemented |
| Chat and citations | Implemented baseline | Quoted source passages and live source previews; generative model optional/unverified |
| Source deletion | Implemented for live DB | Removes file bytes/chunks/jobs and redacts stored answers citing them; browser copies/backups are separate |
| Conversations | Partial | Owned server history, list/get/delete API; UI current conversation only, no branch/edit/regenerate |
| Ollama | Partial | Adapter contract tested; real inference/model licence/hardware evaluation pending |
| Chat SSE | Partial | Validated final-result/done events; no model token streaming |
| Isolated website widget | Authenticated preview | Lazy iframe, Shadow DOM launcher, destroy event; no postMessage commands; guest/domain/host identity pending |
| Typed JS client | Partial | HTTP/errors/abort; no React/Native/Flutter package yet |
| Local booking | Implemented bounded reference | Browse service/absolute slots, create/reschedule/cancel, own bookings, receipts |
| Booking confirmations/idempotency | Implemented | Immutable expiring user-bound operation, atomic capacity, version checks, durable receipts |
| Booking calendar policy | Partial | Seeded weekday schedule, one service resource, fixed 30-minute slots, one-hour lead time, future-only cancellation; no staff/holidays/buffers/capacity editor |
| Reminder delivery | Implemented in-app | Versioned deduplication and scheduled/cancelled/delivered state; worker recovery; API inbox (UI inbox pending); no email/SMS |
| Tool inventory | Partial | Read-only inventory of implemented booking functions; generic registry/JSON schema SDK pending |
| External tools | Unconfigured/unimplemented | No email/calendar/commerce provider; no fake success |
| Docker/PostgreSQL | Unverified | No Docker available here |
| E2E browser tests | Verified in GitHub CI | Two real-browser journeys passed: knowledge/booking and authenticated iframe chat. Local Chromium download remains unavailable. |
| FAQ evaluation | Implemented smoke baseline | Three synthetic cases; not a measured general model benchmark |
| Workflow builder, support inbox, memory | Planned | Not shipped as disconnected screens |
| Full privacy export, audit and analytics | Planned | No unsupported compliance or resolution claims |
| React Native, voice, Flutter, cloud | Optional later milestones | No adapters silently enabled |

Next acceptance work: run PostgreSQL/real-model tests, add local embeddings and streaming, extend calendar policies, then implement generic tool registry, human support, signed client identity and durable workflows. External credentials do not block independent local features.
