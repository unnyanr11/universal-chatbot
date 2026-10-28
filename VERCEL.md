# Vercel deployment

The root `vercel.json` uses Vercel Services (beta). Keep the Vercel project Root
Directory at the repository root; the services set their own roots.

| Component | Public paths | Runtime dependencies |
| --- | --- | --- |
| `app` | Catch-all: `/v1/*`, `/health`, `/`, `/chat.html`, `/demo-embed.html`, API docs | PostgreSQL, configured AI provider; `admin` through `FRONTEND_INTERNAL_URL` |
| `admin` | `/admin`, `/admin/*`, `/widget-loader.js`, `/demo-embed.js` | Static Vite build; browser calls same-origin `/v1/*` |
| `worker` daemon | None | Same PostgreSQL database; optional embedding endpoint and allowed webhook destinations |

`app` consumes the `admin` service binding at request time to fetch only the three
fixed HTML documents. It forwards no user cookies, authorization headers, identity
fragments or query parameters to the static service. The API retains its existing
per-assistant `frame-ancestors` policy for embedded chat. Direct static frontend
responses prohibit framing; use `/chat.html` for public chat and `/` for authenticated
previews. Both load assets from `/admin/`. Existing integration URLs remain valid.

The Vite build has a separate `dist/admin` output on Vercel, exposed from `dist`.
The physical asset paths match the preserved `/admin/` request prefix. The two
public loader scripts are copied to the output root to retain existing embed URLs.
Internal HTML requests honor the deployment's proxy/certificate settings and keep
TLS verification enabled. The normal Docker/native build
still produces the API's bundled `web` directory. Services never depend on another
service's build output. Browser API calls stay relative to the deployment origin;
putting a runtime binding in a `VITE_*` variable would not work and would expose an
internal URL. There is no server-to-server API call from the static admin service.

The daemon uses one `iad1` instance as a proposed default. Choose its region near
your database before production. Daemons run in production, not preview deployments;
preview ingestion/webhooks need a separate worker against the preview database.
`vercel dev` runs services and injects bindings; run the worker separately locally.
Do not assume it starts the production daemon. The worker claims durable jobs in the
database and does not call either service over HTTP, so it needs no service binding.
Docker's `db` and `ollama` hostnames apply only to Compose; those containers are not
Vercel services and their URLs must not be copied into Vercel environment variables.

## Provision before deployment

Using Supabase? Follow [docs/SUPABASE.md](docs/SUPABASE.md) for the pooler connection,
server-only table protection and database cutover. Supabase can replace Neon;
the frontend and API still share one Vercel project.

1. Link the repository to the intended Vercel project/team and connect a persistent
   PostgreSQL database. Use separate databases for production and previews. Never
   run previews against the production database.
2. In Vercel's environment settings, set `DATABASE_URL` to the database connection
   URL and `PROVIDER_SECRET_KEY` to a generated Fernet key. Standard `postgresql://`
   URLs are normalized to the installed psycopg driver. SQLite is rejected when
   `VERCEL=1`, because the filesystem is ephemeral. Neither value belongs in Git.
3. For Gemini set `AI_PROVIDER=gemini`, `AI_MODEL` to your available model ID and
   `AI_API_KEY` to your Gemini key, all server-side. Alternatively, configure provider
   credentials in the authenticated assistant settings after bootstrapping. Leave
   `OLLAMA_MODEL` and `OLLAMA_EMBED_MODEL` empty unless you have a reachable private
   Ollama service. With no embedding model, document retrieval remains lexical.
   Set `WEBHOOK_ALLOWED_URLS` only for destinations you actually use.
4. Set `BOOTSTRAP_OWNER_EMAIL`, a sensitive `BOOTSTRAP_OWNER_PASSWORD` (16–256
   characters) and optionally `BOOTSTRAP_ORGANIZATION` in the production environment.
   The Vercel worker initializes the schema and first owner before processing jobs.
   PostgreSQL transaction advisory locks serialize migrations and initial account
   creation across overlapping worker deployments. Existing accounts are preserved;
   bootstrap never changes an existing password. Remove the bootstrap variables
   after the first successful sign-in. Do not copy them to preview environments.
   Preview databases need separate initialization because daemons run only in production.
   Non-Vercel operators can still run `python -m platform_api.migrate` and
   `python -m platform_api.bootstrap` interactively. Migrations never run in requests.
5. Do **not** define `FRONTEND_INTERNAL_URL` yourself. Vercel injects this binding into
   the API function at runtime. It is not a build variable or a browser API URL.

## Test and release

After linking and configuring a local database, run from the repository root:

```bash
vercel dev
```

Load the matching local environment securely before starting (do not commit `.env`
files). In another terminal using that database, run:

```bash
python -m platform_api.worker
```

Check `/health`, sign in at `/admin/`, upload a text document and wait for indexing.
Then publish an assistant and exercise `/chat.html?assistant=YOUR_ASSISTANT_ID` and
the generated widget snippet. Check that JavaScript loads under `/admin/assets/`,
`/v1/*` returns API responses, the owner invitation URL at `/#invite=...` still works,
and allowed-domain embedding works through `/chat.html` but direct static HTML
cannot be framed. Test real Gemini completion only after configuring the key.

Use Git integration or `vercel` for a preview. After configuring/initializing the
production database and bootstrap variables, stage a production deployment, verify it and promote it.
Database, daemon and AI usage can incur charges. This configuration does not buy
resources, create a Vercel project, provision a database, or establish that a live
deployment has passed its checks.

References: [Services](https://vercel.com/docs/services),
[bindings](https://vercel.com/docs/services/bindings),
[daemons](https://vercel.com/docs/daemons).
