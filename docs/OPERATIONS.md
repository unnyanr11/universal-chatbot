# Operations

## Hardware and cost

Build environment: Python 3.12.14, approximately 9.7 GiB visible system RAM and 29.7 GiB free disk at check time; GPU/VRAM unknown. Docker and Ollama are absent. These observations are not tested inference requirements. The API/test suite ran on CPU; no inference benchmark, memory peak, token throughput or minimum model requirements were measured.

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
