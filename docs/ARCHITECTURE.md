# Architecture and permission model

One Python service owns authentication and server-side policy. Relational SQLAlchemy models support native SQLite and PostgreSQL. Browser/mobile clients will talk to the application API, never directly to Ollama. A provider protocol isolates the model boundary. No generic HTTP connector, code execution or tool dispatch exists yet.

Authentication issues a random bearer token and stores its SHA-256 digest. Tokens expire after one hour and can be revoked by deleting their database session. Permissions are read from membership records on each request. A supplied project identifier is a locator, not proof of access: the API checks authenticated membership in that project's organisation before querying assistants. Inaccessible project IDs return the same 404 as unknown projects. API clients must keep bearer tokens private and use TLS outside loopback; browser storage integration has not been implemented.

| Role | Read own projects/assistants | Create draft assistant | Run inference diagnostic |
|---|---|---|---|
| owner, administrator, developer | Yes | Yes | Yes |
| support_agent, analyst, end_user | Yes | No | No |
| Non-member | No | No | No |

Roles currently share organisation-wide project visibility. Private knowledge and per-project memberships are not implemented. End-user credentials are not exposed publicly; guest access is pending. Other platform permissions have no working endpoints yet.

The database is the only durable state store in Phase 0. No vector database or Redis is required. A database-backed ingestion queue will be added with knowledge ingestion rather than creating an unused worker. PostgreSQL vector search versus a tenant-scoped local index will be selected alongside the embedding model after hardware/licence checks.

Future React/TypeScript admin and iframe widget will be separate clients. They are intentionally absent rather than shipping disconnected mock screens. Initial API contracts are versioned under `/v1`; FastAPI exposes `/openapi.json`. Assistant records start at version 1, but immutable configuration snapshots and publish semantics are pending.

Official references consulted during implementation:
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ — Argon2 password hashing guidance; this app uses opaque sessions instead of JWTs for simple immediate revocation.
- https://github.com/ollama/ollama/blob/main/docs/api.md — `/api/chat` request/response boundary.

No foundation model weights are distributed. Ollama software and selected model weights have separate licences; verify the exact model tag's licence and redistribution terms before enabling inference. No embedding model has been selected. Exact Python package versions are recorded; a reviewed transitive licence inventory and vulnerability scan remain release work. Source code is provided under MIT (see LICENSE); third-party packages retain their licences.
