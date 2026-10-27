# Threat model, limits and retention

This is a local development foundation, not a hardened public service.

| Threat | Existing boundary | Outstanding controls |
|---|---|---|
| Cross-tenant object references | Membership lookup before project/assistant access | Extend checks to all future entities, files, streams and jobs |
| Token/database disclosure | Random tokens; only token digests and Argon2 passwords stored | TLS/reverse proxy, disk encryption, incident procedures |
| Password guessing | Database-backed global login budget and dummy password verification | Per-account/IP budgets, proxy trust configuration; global budget can be exhausted as denial of service |
| Stolen sessions | One-hour expiry and current-session logout | Session management, all-session revocation, credential rotation |
| Malicious generated text | Diagnostic returns plain JSON, no HTML/tool execution | Safe Markdown renderer and structured action records in future UI |
| Model/network abuse | Operator-owned model URL; no client URL input; generation budget | Concurrency limits, total request deadlines, body limits at proxy |
| Secret exposure | Validation errors omit raw submitted values; no request logging | Redacted audit log, encrypted connector credentials when introduced |

No cookies are used, so authentication is explicit bearer authorization rather than cookie-based sessions. No cross-origin browser access is enabled. UI integration must deliberately configure restricted origins and, if cookies are introduced, CSRF protection. Swagger documentation is for local development.

There are no external tools or financial actions. Model output cannot confer identity or permission. RAG prompt injection tests will accompany ingestion; an adapter contract test is not an injection-resistance claim.

Database records persist until the operator removes them. Session expiry blocks access but does not automatically delete expired records. Expired-session cleanup, user export/deletion, document deletion, retention configuration and audit logs are pending. No general-purpose memory, raw documents or integration secrets are stored yet. Backups contain credentials (hashed), tenant records and session digests; protect them and define expiry before using real data.

Use synthetic data only for this release. Environments must use separate databases and credentials; environment-specific credential validation is pending. Do not set APP_ENV=production expecting hardening to happen automatically. Demo seeding refuses non-development mode.

Report suspected vulnerabilities privately to the repository maintainer; no public reporting address has been configured. Include version and a minimal synthetic reproduction without secrets. Do not publish exploit payloads containing user data.
