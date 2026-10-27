# Operations

## Hardware and cost

Build environment: Python 3.12.14, approximately 9.7 GiB visible system RAM and 29.7 GiB free disk at check time; GPU/VRAM unknown. Docker and Ollama are absent. These observations are not tested inference requirements. The authoring API/test suite ran on CPU without a local model server. Separate CI model observations are recorded in BENCHMARKS.md; no minimum hardware or production throughput is inferred.

The application has no paid API dependency. Source-passage mode needs no model. Downloading model weights requires network/storage; CPU/GPU inference uses electricity and hardware capacity. Public hosting, delivery services and cloud inference can incur costs. No unlimited or always-on free service is promised. Select models only after measuring target hardware and reviewing licences.

## Backup and restore

Stop the native API before copying `assistant.db` to an access-controlled backup. Restore while stopped, preserve file permissions and run the migration command before restart. Never back up a live SQLite file by blindly copying it. An alternative is the SQLite online backup API.

For Compose, use `docker compose exec -T db pg_dump -U assistant -d assistant > backup.sql`. Restore only into an empty database using `docker compose exec -T db psql -U assistant -d assistant < backup.sql`, then run migration and smoke tests. These PostgreSQL commands are documented but not executed here. Model volumes contain redownloadable assets; source bytes and extracted knowledge now live in the relational database.

## Troubleshooting

- Missing tables: run `python -m platform_api.migrate` with the same DATABASE_URL as the API.
- No projects: verify seed completed, account identity and active membership.
- 401: session may be expired/revoked; authenticate again.
- 404 on project: membership denied and missing objects intentionally share a response.
- 429 at login: wait until the next minute; the budget is shared and durable.
- 503 inference: check OLLAMA_MODEL, exact installed tag and model-server reachability. No fallback completion is generated.
- Compose seeding failure: use a unique password at least 16 characters and APP_ENV=development.

In-app reminder records are real local notifications. No email/SMS delivery, deployments or external accounts were created. Publish only after reviewing the security backlog and completing missing checks.

## Updated release operations

Always run `python -m platform_api.migrate` before starting an updated checkout; the current additive schema revision is 7. Stop services and take an authorised backup before upgrading an existing deployment. The migration refuses a newer unsupported schema version. These revisions add tables; future destructive/type changes require explicit reviewed migrations.

The worker handles ingestion leases, reminder delivery and expired session/invitation/preference cleanup. If the database is temporarily unavailable, Compose restarts the worker; a native operator may need to restart its process. Workflow runs checkpoint in the database. The Workflows UI can recover an interrupted run after its 90-second lease expires, without replaying a completed booking.

Changing a managed service policy invalidates pending approvals and old availability bindings. Generate new availability for the desired future date window afterward. Already confirmed bookings remain reserved; changing a policy is not a mass cancellation. Staff resources are capacity one; do not model multi-seat resources without extending and testing the allocator.

Use `python -m platform_api.bootstrap` for the first non-demo owner in an empty database. The Team screen creates local one-time invitation links, not email delivery. The Privacy screen supports password rotation and all-session logout; account recovery requires an operator procedure and is not an automated email/SMS feature.

CI has verified the Compose stack and real local model runtime; see VERIFICATION.md and BENCHMARKS.md. Those measurements are CPU smoke observations, not minimum hardware or uptime guarantees. Store model volumes separately from protected data backups if desired; source bytes/embeddings and user records live in the relational database.

## Guided installer

`python3 scripts/setup.py` configures and checks the local Docker stack. It generates `.env` with restrictive file permissions on Unix, preserves existing database passwords, creates the first owner/assistant and a product guide, and pulls the configured local models. Rerunning resumes setup without creating demo identities or rotating existing account credentials. Do not remove `.env` while retaining an existing PostgreSQL volume: the database keeps its original password. Restore the original `.env` from protected backup if lost; generating a new password does not change an existing database's password.

The public-domain option adds `compose.public.yaml` and Caddy. DNS and inbound TCP ports 80/443 must already reach the server. Setup verifies public HTTPS before declaring completion. Caddy certificate state is persisted in the `certificates` volume. Localhost remains the default. Restarting a domain installation manually requires both compose files: `docker compose -f compose.yaml -f compose.public.yaml up -d`. For logs use the same files with `logs --tail=100`; never post `.env` or owner credentials in support messages.

The installer checks real model completion, embedding generation and newly created guide ingestion. It does not certify model answer quality or configure external providers, mail delivery, DNS or real business staff/policies. See STATUS.md for those boundaries. Public TLS issuance is conditional on the operator's domain; CI validates Caddy configuration, while actual certificates are checked by the installer at deployment time.

Cloud provider configuration and encrypted key backup/restore are documented in PROVIDERS.md. Always preserve PROVIDER_SECRET_KEY across container recreation and updates; regenerating it makes stored per-assistant keys unreadable. The wizard reuses it and existing database credentials. Cloud readiness failure stops setup rather than silently switching to Ollama. Model/account-specific failures return sanitized PROVIDER_* codes; check the selected model, key, budget and provider account status.
