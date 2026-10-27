# Threat model and implemented controls

This development preview should use synthetic data on loopback. It is not a public-production security claim.

| Threat | Existing control | Remaining work |
|---|---|---|
| Cross-tenant IDs | Authenticated membership checks on project/assistant routes; own-user checks on bookings/conversations/operations | Extend controls with every new feature; narrower project membership |
| Credential disclosure | Argon2 passwords, hashed opaque one-hour session tokens, memory-only browser token | TLS/reverse proxy, session administration, credential rotation |
| Password guessing | Durable atomic global 20-attempt/minute budget; dummy password verification | Per-account/IP limits, proxy trust; global budget is susceptible to denial of service |
| Upload bombs | 2 MB read cap, extension and content checks, subprocess timeout; Unix resource budgets; DOCX expansion limits | Total multipart body limits at proxy, sandbox hardening; Windows lacks Unix resource limits |
| Document prompt injection | No generated tool execution, no arbitrary HTTP/SQL/shell, quoted source mode, model boundaries | Broader adversarial/model evaluation; no prompt-only guarantee |
| Race/duplicate actions | User-bound immutable proposals, expiry, database reservation uniqueness, atomic transactions, versioned approvals | Multi-resource capacity; PostgreSQL backend suite passed in CI |
| Stale citation content | Live source scope checks, source deletion and transcript redaction | Browser/downloaded copies and backups cannot be recalled |
| Model exhaustion | Single completion gate per API process, bounded context/output and total deadline | Deployment-wide admission/quotas and fair queuing |
| UI injection | React text rendering, no untrusted HTML/Markdown execution, static loader with no message bridge | Browser acceptance, CSP hardening and host identity |
| Secret leaks in errors | Validation errors omit raw inputs; no raw model/document/request logging | Redacted audit and access logs, encrypted connector credentials when added |

No cookies or cross-origin CORS access are enabled. Requests use explicit bearer authorization. If future clients use cookies, add CSRF protection. Do not expose Swagger or diagnostic inference publicly without deployment review. The server-controlled Ollama URL is not a client-configurable proxy; no general outbound HTTP connector exists.

## Retention and deletion

Original file bytes, chunks, conversations, operation records, bookings and reminders are durable database records. Source deletion removes bytes/chunks/jobs and redacts stored assistant answers that cited them. It cannot erase text already copied to a user message, downloaded to a browser, or retained in an old backup. Conversation deletion removes the owned conversation/messages. No cache or general-purpose memory exists.

Accounts, expired sessions, operation receipts and cancelled booking records are currently retained indefinitely until operator-managed removal. Full account export/deletion, expiry cleanup, configurable retention and audit retention are unimplemented; establish those before using real customer data. Protect backups and expire them under an operator policy. No external services hold replicated user data from this code.

Demo seeding refuses APP_ENV other than development; no fixed password is shipped. Setting production mode does not automatically harden a deployment. Use separate databases/credentials for each environment. Report vulnerabilities privately to the repository maintainer with a synthetic reproduction; no reporting address has been configured.
