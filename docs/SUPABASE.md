# Supabase database backend

Supabase Postgres can replace Neon or another PostgreSQL host without rewriting the
application's transactional API. The React frontend, FastAPI functions and private
worker remain in one Vercel project. Existing application sessions, tenant roles,
bookings and workflows continue to be enforced by the application API. Supabase
Auth, Storage and Edge Functions are not enabled by this database integration.

## Connection

Use the **Transaction pooler** connection string from the Supabase project's
**Connect** dialog for Vercel. Copy the actual pooler hostname and username; the
hostname cannot safely be inferred from the region. The shared transaction pooler
uses port **6543** and supports IPv4. Replace the password placeholder privately,
percent-encoding reserved characters in the password.

Set this string as the production **Secret** `SUPABASE_DATABASE_URL` in Vercel, then redeploy
both services and the worker. This is a PostgreSQL connection string, not the
Supabase HTTPS project URL or a publishable/service-role API key. No Supabase API
key or database password belongs in a `VITE_*` variable or client-side JavaScript.
Use a separate database for previews. Never attach a preview to production data.
`SUPABASE_DATABASE_URL` takes precedence over `DATABASE_URL` in every runtime and
operator entrypoint. This allows the Neon integration to remain connected until
the Supabase cutover is verified; no integration-managed secret needs overwriting.

The existing psycopg driver accepts standard `postgresql://` URLs. Supabase hosts
automatically use `NullPool` behind Supavisor and disable prepared statements.
TLS is required by default; an explicit stronger `sslmode` is preserved. Do not
disable TLS. The worker uses transaction-scoped advisory locks for migrations and
first-owner creation, compatible with transaction pooling.

## Schema and authorization

The ORM and `platform_api.migrate` remain the schema source of truth. The worker
initializes missing tables on production startup. On recognized Supabase hosts,
migration also enables RLS on every application table and revokes table privileges
from `PUBLIC`, `anon` and `authenticated`. There are deliberately no browser RLS
policies: clients call authenticated `/v1` routes instead of querying tables through
the Supabase Data API. The server database role must own the application tables or
have the required privileges and RLS bypass. Keep its connection string private.

Supabase's managed `auth` and `storage` schemas are not modified. Review security
advisors after schema changes; an informational notice about RLS without policies
is expected for these deliberately server-only tables.

## Cutover

For an empty deployment, initialize the Supabase schema and supply the bootstrap
owner and Gemini secrets described in [VERCEL.md](../VERCEL.md). For a database
with existing business data, back it up and migrate/verify that data before changing
the production connection. Changing a connection variable alone does not copy data.
Retain the old database until the new deployment and data have been verified.

Verify the schema revision, table count, RLS and revoked grants through Supabase,
then check the deployed login, health endpoint, owner account, ingestion worker and
an authenticated Gemini request. A successful SQL query alone does not prove the
Vercel deployment uses the new database.

References: [Supabase connections](https://supabase.com/docs/guides/database/connecting-to-postgres),
[database security](https://supabase.com/docs/guides/database/secure-data),
[psycopg prepared statements](https://www.psycopg.org/psycopg3/docs/advanced/prepare.html).
