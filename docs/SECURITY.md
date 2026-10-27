# Security boundaries and retention

The verified release is a self-hosted local platform. It has not received an independent production-security or compliance audit.

| Threat | Implemented boundary | Remaining operational work |
|---|---|---|
| Cross-tenant IDs | Membership-derived project/assistant access and user-owned conversation/action/booking/run checks | Document-level per-group ACLs and custom project roles are not provided; approved sources are organisation-member knowledge |
| Credential disclosure | Argon2 passwords; hashed opaque one-hour sessions and one-time invitation tokens; memory-only browser sessions; password/all-session revocation | TLS, encrypted disks/backups and deployment key/secret management |
| Password guessing | Durable atomic global login budget and dummy password verification | Per-IP/account reverse-proxy throttling; the global local-profile budget can be exhausted as denial of service |
| Upload/JSON exhaustion | 2.1 MB pre-parser request bound (including chunked bodies), 2 MB file limit, signatures/UTF-8 checks, bounded subprocess extraction | Windows lacks Unix memory/CPU limits; retain wall-clock limits and use trusted/synthetic local uploads until the parser environment is hardened |
| Prompt injection | Documents/context are untrusted; model output is text only; typed server-created controls; allowlisted tools; no SQL/shell/code/HTTP dispatch from text | Broader adversarial/model-quality evaluation; no prompt-only or zero-hallucination guarantee |
| Duplicate/racing writes | User-bound expiring operations, idempotency, slot uniqueness, staff guard rows, atomic rescheduling and policy/version checks | Multi-seat/resource capacity and arbitrary-provider reconciliation are not implemented |
| Stale or removed evidence | Live citation checks, source/index removal and cited-transcript redaction; final inference access checks | Already streamed/downloaded text and old backups cannot be recalled |
| Model exhaustion | Per-process completion admission, bounded context/output/deadline and worker embedding budgets | Deployment-wide fairness, quotas and queue monitoring |
| Client injection/framing | React text rendering, no raw generated HTML, strict JSON actions, CSP frame-ancestors configured for the widget, no generic postMessage bridge | Native device acceptance and signed host identity; an allowed domain is not authentication |
| Handoff leakage | Only agents may claim/reply/note; internal notes are separate records, excluded from customer transcripts/model context/exports | Presence/availability service and real-time agent delivery are not implemented |

The application uses bearer headers rather than authentication cookies; no cross-origin API CORS access is enabled by default. Cookie-based integrations would require CSRF controls. Do not expose diagnostic inference or administrative docs publicly without deployment review. The operator-owned Ollama URL is not a user-configurable network proxy. Generic external connectors remain disabled, avoiding an unrestricted SSRF surface.

## Invitations and membership

Invitation links are one-time, email/role/organisation-bound and expire after 24 hours. The token is returned once for local sharing and stored only as a digest; it is placed in a URL fragment rather than server request paths. No email is sent. Existing accounts must authenticate to accept; an invite cannot silently replace an account or upgrade an existing membership. Only owners can invite/remove privileged owners/administrators. The last owner cannot be removed. Membership removal revokes sessions, cancels pending operations/runs and releases assigned tickets back to the queue.

Bootstrap is explicit and restricted to an empty account database. Development seed refuses non-development APP_ENV and requires an operator-supplied password. No production/demo password is shipped.

## Retention and user controls

- Source deletion removes the live file bytes, chunks, embeddings and ingestion job, and redacts stored assistant answers citing that source. Published manifests retain source IDs/hashes for lineage, without passage bytes. User-authored messages may still contain text they copied themselves.
- Conversation deletion removes owned messages, chat-action cards and associated handoff/notes. Executed bookings and their operation receipts remain independent; transcript deletion does not silently cancel an appointment.
- Workspace export contains owned conversations, bookings, operation records, workflow runs and preferences. Private agent notes are excluded. Workspace erasure removes those live user records and frees reservations, including staff capacity. It leaves the account, memberships and shared business knowledge intact.
- Preferences require explicit consent, expire after at most 90 days and can be forgotten. Up to three active, user-owned preferences may guide local-model tone/style; they cannot grant permissions or serve as factual evidence. The worker deletes expired preference, invitation and session records.
- Booking/history/operation/audit data otherwise remains until explicit erasure or operator retention policy. Existing audit actor references are pseudonymised during workspace erasure. Audit events contain object/action references, not message bodies or integration credentials.
- No automatic backup expiry, full account deletion, legal-hold/compliance mechanism or external-provider deletion is claimed. Protect and expire backups under an operator policy. No general-purpose integration secret store exists because no external credential-based adapter is enabled.

Use separate databases/credentials/deployments for development, staging and production. Project environment labels do not themselves isolate server credentials. Report suspected vulnerabilities privately to the repository maintainer with synthetic reproductions; no reporting email has been configured.
