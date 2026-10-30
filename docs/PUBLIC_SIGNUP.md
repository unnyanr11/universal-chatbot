# Public accounts

Public signup uses Supabase Auth for email/password accounts and email confirmation.
Existing local/bootstrap/invited accounts keep their existing login. A confirmed
Supabase account cannot take over an existing local account just by sharing its email.
New users receive one private organization, an owner membership, a project and an
assistant. Supabase user metadata is used only for the workspace's display name;
it never supplies a role or an organization identifier.

## Operator setup

1. Keep `PUBLIC_SIGNUP_ENABLED=false` while preparing email delivery.
2. Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in the target Vercel project's
   Production environment. A legacy `SUPABASE_ANON_KEY` is also supported. Never
   use a service-role key for this flow. `SUPABASE_DATABASE_URL` and the existing
   `PROVIDER_SECRET_KEY` are still required by the application API.
3. In Supabase Auth, enable email signup and keep email confirmation enabled.
   Configure custom SMTP with your sender domain. The default Supabase mail service
   only delivers to project team addresses, so it cannot support public signups.
4. Set Supabase Auth's Site URL and allowed redirect URL to the actual public app
   URL (for this project: `https://universal-chatbot-eight.vercel.app`). Set
   `PUBLIC_APP_URL` to that same URL. Confirmation links return users to sign-in;
   URL tokens are discarded, and only a server-verified password exchange opens
   an application session.
5. Run `python -m platform_api.migrate` against the production database, or let the
   worker migrate before opening signups. Schema revision 10 adds `public_accounts`
   and `public_workspaces` without changing existing accounts. Both tables use the
   same server-only RLS/revoked Data API privileges as the other application tables.
6. Set `PUBLIC_SIGNUP_ENABLED=true`, redeploy, and test with an email outside your
   Supabase project team: register, confirm the email, sign in, add an AI key,
   upload a source, test a reply, publish and install. Do not announce public
   availability until that complete flow passes.

Closing signups does not lock out existing public accounts. Existing account login
still requires the Supabase URL/key. Never remove the public-account policy rows
to restore a deployment default: that would allow an unintended use of operator AI.

## Boundaries and limits

Public workspaces never inherit the operator's cloud API key or local Ollama model.
Users supply an encrypted assistant-specific cloud key in Settings. Disconnecting
that key returns the assistant to an unconfigured, source-based mode. The legacy
deployment inference diagnostic is forbidden for public workspaces. Additional
organizations created by public users retain the same policy.

There is a global budget of 10 registration requests per minute and the existing
20 login requests per minute, plus Supabase Auth's rate limits. Public accounts
can own up to three workspaces; each public project can have ten assistants, and
each assistant can have fifty sources of at most 2 MB each. Website imports use
the same source limit. PostgreSQL row locks serialize quota checks. These are
initial beta safeguards, not a billing or unlimited-storage service.

The application uses expiring, revocable opaque sessions after Supabase sign-in,
not Supabase tokens for Data API access. Password recovery UI, billing, automated
account deletion and CAPTCHA are not included in this release. Configure Supabase
abuse protections and adjust rate limits before scaling beyond a small beta.
