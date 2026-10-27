# Architecture and data flow

One FastAPI application owns authentication, tenant policy, knowledge, chat and bookings. One Python worker leases database jobs for extraction and delivers in-app reminders. React/TypeScript and the iframe widget are clients of the same application API. Ollama stays behind the application boundary. PostgreSQL is the Compose target and its backend suite passed in CI; SQLite is the verified native profile. No Redis, vector database, Kubernetes or microservice fleet is required.

## Boundaries

Opaque random bearer tokens are stored only as SHA-256 digests, expire after one hour and are immediately revocable. Every feature route derives identity from the session and checks the requested project/assistant through organisation membership. User-owned conversations, operations and bookings additionally compare the authenticated user ID. Client/project identifiers locate objects; they never grant access.

| Role | Read own organisation's projects and approved sources | Create assistant / upload/delete sources | Own conversations / bookings |
|---|---|---|---|
| owner, administrator, developer | Yes | Yes | Yes |
| support_agent, analyst, end_user | Yes | No | Yes |
| Non-member | No | No | No |

Project visibility is currently organisation-wide. No public guest account exists. Membership invitations, narrower project permissions and role management are pending. Development/staging/production should use separate databases and credentials; project environment labels alone do not isolate credentials.

## Knowledge

An authorised upload validates extension, signature/UTF-8 and size, hashes bytes for deduplication, then creates a document and job atomically. The worker uses an atomic lease with a random ownership token. It runs extraction in a subprocess with wall-clock and (on Unix) memory/CPU budgets. Parsing never executes macros or fetches links. A successful lease persists page-aware chunks and final status in one transaction; a deleted document cannot be resurrected by a worker. Expired leases recover after restart with a three-attempt budget.

Bounded original files are stored as relational BLOBs for this development slice. This deliberately avoids a second, unverified filesystem lifecycle; a tenant-authorised storage adapter for larger files is future work. PDFs use pypdf without OCR. DOCX extracts `word/document.xml` after archive expansion checks and has no reliable rendered page metadata (logical page 1). CSV is indexed as UTF-8 passages, not a typed FAQ import.

Retrieval is a small lexical TF/IDF-style baseline over up to 5,000 accessible chunks. It returns up to four passages. Scores are not confidence. Semantic embeddings/hybrid search and reranking are pending. Source-passage chat quotes evidence rather than claiming AI inference. Local-model mode passes only retrieved material with a question, validates citation index bounds and stores the answer with live citation IDs. A valid citation index cannot prove that an AI claim is correct. No generated HTML or action is executable.

Deleting a source removes its bytes, chunks and job; answers citing those chunks are replaced with a redaction notice. Source IDs resolve against current access each time. A final-result SSE response exists, but model token streaming is not implemented. Conversation messages are user-owned and exportable via GET as JSON; full account export/deletion is pending.

## Booking actions

The service exposes an explicit slot catalogue with absolute timestamps and business timezone. Model text never creates a slot or a booking. A proposal record binds kind/slot/booking version to the user/project, has an idempotency key and ten-minute expiry, and produces an exact preview. Confirm rechecks session membership and ownership, claims the operation with a compare-and-swap, and atomically changes reservations/bookings/reminders and receipt state.

A unique reservation primary key makes one-slot capacity a database invariant. Rescheduling releases the original and reserves the replacement inside one transaction: any capacity conflict rolls the whole transaction back. Optimistic booking versions invalidate stale approvals. Retrying the same successful operation returns its existing receipt. After a client timeout, GET the operation or repeat confirmation with the same ID to reconcile the committed local result. No exactly-once guarantee is made for future arbitrary providers.

Reminder delivery is an in-app database state transition, not an email simulation. Version checks suppress stale reminders after cancellation/rescheduling. The inventory labels external email unconfigured. General imported tools/OpenAPI/HTTP connectors are not enabled.

## UI and clients

React screens are split by concern, with a shared controller hook and a small typed HTTP client. Tokens stay in memory and never enter URLs, bundles, iframe loader attributes or analytics. The preview loader lazily mounts an iframe, isolates launcher styles in Shadow DOM, and accepts no postMessage commands. Use a dedicated origin for the widget in a host application; same-origin embedding does not isolate it from a hostile host. Guest sessions and signed host identity are pending.

## References and licences

Official documentation consulted:
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ — Argon2 guidance (opaque sessions are used here for immediate revocation).
- https://fastapi.tiangolo.com/tutorial/request-files/ — bounded UploadFile handling.
- https://github.com/ollama/ollama/blob/main/docs/api.md — local chat boundary.
- https://pypdf.readthedocs.io/en/stable/user/extract-text.html — text extraction and OCR limits.
- https://react.dev/learn/typescript and https://vite.dev/guide/ — typed React build.

Python and JavaScript dependencies are pinned in their lock files. Source is MIT; third-party packages retain their licences. No model weights are bundled. Ollama software and model weights have separate terms; approve an exact model tag, hardware footprint and licence before enabling it. A complete licence inventory and vulnerability scan remain release gates.
