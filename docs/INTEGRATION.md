# Guided deployment and integration

## A short launch path

1. Run `python3 scripts/setup.py` (Windows: `python scripts/setup.py`) on your machine/server. Docker with Compose v2, Git and Python 3.10+ are the host prerequisites. The wizard prepares the application, database, worker, model/provider and first owner. Public HTTPS requires your domain DNS and open ports 80/443.
2. Sign in and open **Integrate → Guided onboarding**. Apply FAQ, enquiry, support or appointment templates to the draft. These templates contain instructions/questions, not invented business facts, staff or availability.
3. Upload approved documents in Knowledge, or fetch a selected public HTTPS website page in Integrate. Review the extracted text and explicitly approve import. Wait for indexing. Optionally apply the suggested theme colour/web-safe font to the draft.
4. Create a private draft preview. It uses an isolated 10-minute session and includes unpublished knowledge. Real booking, enquiry and handoff writes are disabled. Do not share this privileged preview URL; its token is carried in the URL fragment and removed from the address bar on load.
5. In Settings, review branding/questions, add allowed embedding host names without schemes/paths, save and publish. Use Version history's Restore button for one-click content rollback; removed documents stay removed. Provider credentials and public integration controls are operational and are not rolled back with content.
6. In Integrate, enable public chat, optionally enable enquiries/human support/verified appointments, set a daily public-message limit, save and copy the public embed snippet. Alternatively share the chat-page URL or download the WordPress plugin.
7. Run the installation checker, then open your website, click the widget and test a question. The checker verifies readable static HTML, the expected loader/assistant ID, published domain allowance and public enablement. It cannot prove browser JavaScript execution, runtime CSP or scripts inserted dynamically; the real browser test is still required.

An FAQ chatbot can launch without appointments, lead collection or webhooks. Appointments need real staff/services/availability in Calendars. Support queues need a staffed business process; in-app handoff does not promise instant service. AI provider keys remain on your server; no visitor sees those credentials.

## Public and signed sessions

The public loader uses `data-public="1"`. It opens `/chat.html?assistant=...`, creates a constrained guest session and renders the published assistant. Visitors can ask sourced questions, inspect citations, delete their current conversation, submit an explicitly consented enquiry when enabled and request human support. The old authenticated loader remains available without data-public, so existing integrations keep their sign-in flow.

Guest credentials are ordinary short-lived opaque bearer tokens with an additional server-enforced assistant scope. They cannot access Studio projects, admin configuration, knowledge documents, provider credentials, other assistants or other visitors' conversations. Guest chat retrieves only the current published source manifest. Public message attempts have an atomic per-assistant UTC-day limit, issuance is limited per minute and per day, and integration revision changes revoke existing public sessions. These are request-count limits, not a currency spending cap or comprehensive bot defense. Deploy additional reverse-proxy abuse controls before offering a large public service.

Private appointment access and booking writes require verified host identity. Configure a signing secret in Integrate; it is returned once and encrypted on the server. Your own authenticated backend signs an assertion using `examples/signed_identity.py` or the WordPress filter example. Derive the subject from your authenticated website session, never from an unverified browser-supplied ID. The format is `base64url(JSON).base64url(HMAC-SHA256(secret,payload))` with assistant_id, sub, exp (up to five minutes ahead) and a random nonce. Assertions are one-use, expire and map to a stable customer identity separately for each assistant. They do not link to Studio accounts by email or bypass booking approval.

Supply the assertion in the loader's `data-identity` attribute. The loader transfers it in the iframe URL fragment, removes the attribute, and the frame consumes it. The signing secret must never be in HTML or a browser bundle. Do not cache signed pages across customers. Sessions last up to one hour; destroy the widget when the host logs out using the loader's `assistant:destroy` event. Tokens are kept in memory. A signed assertion is not a general JWT or an OAuth integration.

Public contacts and conversations remain business records; conversation deletion removes the current transcript, while enquiry deletion is available to business staff. The existing owned workspace export/erasure includes enquiry data for authenticated accounts. Accounts/shared knowledge/backups remain subject to the documented retention boundaries. Anonymous sessions do not gain access to unrelated private account records.

## Website import and styling

Import fetches only a user-selected public HTTPS HTML page, at most 2 MB per response. It validates all DNS answers, rejects private/reserved/multicast destinations and custom ports, and connects to a validated IP while preserving TLS host verification. Redirects are bounded and restricted to the same host. It does not forward cookies, credentials or ambient proxies. HTML scripts/styles are excluded, text is bounded, and the review expires after 15 minutes. The owner must approve the extracted text before a durable ingestion job is created. Fetch further pages individually; no recursive crawler, login automation, JavaScript rendering or OCR is claimed. Only import material you are authorised to use.

Styling suggestions come from an explicit six-digit theme-colour meta tag and supported inline web-safe font families. They are suggestions, not a full CSS/brand analysis. Applying them changes the draft; publishing applies them to public chat. No arbitrary stylesheet, HTML or external font code is imported.

## WordPress

Download the ZIP in Integrate, then Plugins → Add New → Upload Plugin → activate. In Settings → Universal Chatbot, set the application origin, assistant ID and Enable chatbot. No AI key or administrator application token belongs in WordPress settings. The plugin uses WordPress's Settings API, capability/nonce-protected settings form and frontend script enqueue hook. Deactivating it or unchecking Enable removes the widget; settings are retained for reinstall. Delete the ucb_settings option to remove saved public identifiers.

Allow the WordPress website host in Studio and publish it. If your site uses CSP, permit the application origin in script-src and frame-src. Caches/optimisers that remove script data attributes may need an exclusion for widget-loader.js. Use `examples/wordpress-identity.php` only with a private backend secret and correct per-user cache exclusions. The plugin does not provision hosting or change DNS/CSP automatically.

## Other clients

- `examples/widget.html`: standard HTML loader.
- `examples/react.tsx`: typed React integration with a regular application/guest session token.
- `examples/api_client.py`: actual guest session and sourced-chat API requests.
- `packages/js-sdk`: authenticated JSON/SSE client with cancellation.
- `examples/signed_identity.py`: backend identity assertions.
- `examples/webhook_receiver.py`: receiver signature/freshness verification helper; receivers must persist deduplication themselves.

The iframe avoids cross-origin API integration work. Direct custom browser clients remain same-origin by default; use your own same-origin backend proxy when embedding a custom UI on another origin. Never place upstream AI keys in client code. Native mobile remains a source example needing device acceptance.

## Signed webhooks

The server operator approves exact public HTTPS receiver URLs in WEBHOOK_ALLOWED_URLS and recreates the API/worker with that environment. An owner/administrator enables a receiver in Integrate and saves its once-returned signing secret on the receiving backend. Up to five receiver records are allowed per project. The project scope is explicit: all enabled receivers get booking.confirmed (including reschedules, distinguished by kind), booking.cancelled, support.opened and lead.created events for that project. No transcript, enquiry message or contact details are in webhook payloads; authorised systems can fetch relevant records through the application API.

Events enter a durable outbox in the same transaction as the local effect. The worker leases deliveries, signs exact JSON bytes with timestamp + '.' + body, and sends X-Assistant-Event, X-Assistant-Timestamp and X-Assistant-Signature (`sha256=...`). Verify the timestamp/signature with a constant-time comparison, then deduplicate the stable event ID atomically. Delivery is at least once: a lost receipt can cause a retry. Five attempts use bounded backoff; delivery status/errors are visible in Integrate. Disabling an endpoint cancels pending work but cannot recall an HTTP request already sent. Redirects and private DNS targets are rejected. Real receiver delivery requires your explicit approved configuration; no external endpoint was contacted during authoring.

## Backups and updates

For Compose PostgreSQL installations:

```bash
python3 scripts/maintenance.py backup --output /secure-backups/assistant.dump
python3 scripts/maintenance.py verify-backup --input /secure-backups/assistant.dump
python3 scripts/maintenance.py upgrade --backup /secure-backups/before-upgrade.dump
```

Create the protected backup directory first. Files are created with private Unix permissions, refuse overwrite and must be outside the source checkout. pg_dump provides a consistent database snapshot while services run. Back up `.env` separately in protected storage: it contains the database password and encryption key needed to read stored provider/signing credentials. Model weights are redownloadable.

Upgrade requires a clean source checkout, records the previous Git commit, backs up first, accepts only a fast-forward pull, stops API/worker and reruns setup/migrations/readiness without rotating existing secrets. If a step fails, it stops with the original backup retained; it does not pretend to undo schema changes. Use a tested backup and the matching source/config for rollback, with an operator-controlled maintenance window.

Restore only into a separately prepared empty database:

```bash
python3 scripts/maintenance.py restore --input /secure-backups/assistant.dump --confirm-empty-database
```

The command refuses populated targets, stops API/worker and uses a single-transaction pg_restore. It does not delete an existing database or volume. An optional --database selects a separately created safe database name for restore testing. Reconcile DATABASE_URL/configuration for that database before serving it. For native SQLite, retain the stopped-file/SQLite online-backup procedure in OPERATIONS.md.

## Verification boundaries

The automated suite exercises public isolation, published-vs-preview source separation, assertion expiry/replay, quotas, explicit website review, DNS target rejection, style extraction, scoped enquiries and signed durable webhook retry. Browser acceptance covers actual guest iframe chat, enquiry submission and private draft preview. CI additionally activates/deactivates the plugin on real WordPress/MySQL and tests a PostgreSQL backup/restore round trip. See VERIFICATION.md for observed results; a newly added check is not evidence it passed until the source run completes. Public hosting, DNS, real private business pages, third-party receiver delivery, live paid cloud accounts, native mobile and a production security assessment remain deployment-specific checks.
