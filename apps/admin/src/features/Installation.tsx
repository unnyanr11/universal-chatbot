import { useEffect, useState } from "react";
import { client } from "../model";
import { ErrorNotice, useResource, useTask } from "./shared";
type Integration = {
  revision: number;
  enabled: boolean;
  lead_capture: boolean;
  support_enabled: boolean;
  bookings_enabled: boolean;
  daily_limit: number;
  published: boolean;
  has_identity_secret: boolean;
};
export function Installation({ assistant }: { assistant: string }) {
  const root = `/v1/assistants/${assistant}`;
  const [tick, setTick] = useState(0),
    [draft, setDraft] = useState<Integration>();
  const data = useResource<Integration>(root + "/integration", tick);
  const [host, setHost] = useState("");
  const [check, setCheck] = useState<Record<string, unknown>>();
  const [secret, setSecret] = useState("");
  const [notice, setNotice] = useState("");
  const job = useTask();
  useEffect(() => setDraft(data.data), [data.data]);
  const snippet = `<script defer src="${location.origin}/widget-loader.js" data-public="1" data-assistant="${assistant}"></script>`;
  return (
    <section className="panel">
      <h2>Publish and install</h2>
      <ErrorNotice error={job.error || data.error} />
      {draft && (
        <>
          <p>
            {draft.published
              ? "Published content is available. Allow your website host in Settings and publish again after changing it."
              : "Save and publish approved content in Settings before enabling public chat."}
          </p>
          <label>
            <input
              type="checkbox"
              checked={draft.enabled}
              onChange={(event) =>
                setDraft({ ...draft, enabled: event.target.checked })
              }
            />{" "}
            Enable public guest chat
          </label>
          <label>
            <input
              type="checkbox"
              checked={draft.lead_capture}
              onChange={(event) =>
                setDraft({ ...draft, lead_capture: event.target.checked })
              }
            />{" "}
            Offer enquiry capture with visitor consent
          </label>
          <label>
            <input
              type="checkbox"
              checked={draft.support_enabled}
              onChange={(event) =>
                setDraft({ ...draft, support_enabled: event.target.checked })
              }
            />{" "}
            Offer human support handoff
          </label>
          <label>
            <input
              type="checkbox"
              checked={draft.bookings_enabled}
              onChange={(event) =>
                setDraft({ ...draft, bookings_enabled: event.target.checked })
              }
            />{" "}
            Offer appointments with verified customer identity
          </label>
          <label>
            Daily public-message limit (UTC)
            <input
              type="number"
              min={1}
              max={10000}
              value={draft.daily_limit}
              onChange={(event) =>
                setDraft({ ...draft, daily_limit: Number(event.target.value) })
              }
            />
          </label>
          <button
            disabled={job.busy}
            onClick={() =>
              job.task(async () => {
                await client.request(root + "/integration", {
                  method: "PUT",
                  body: JSON.stringify({
                    revision: draft.revision,
                    enabled: draft.enabled,
                    lead_capture: draft.lead_capture,
                    support_enabled: draft.support_enabled,
                    bookings_enabled: draft.bookings_enabled,
                    daily_limit: draft.daily_limit,
                  }),
                });
                setTick((value) => value + 1);
                setNotice(
                  "Integration saved. Existing public sessions must reconnect after a change.",
                );
              })
            }
          >
            Save public integration
          </button>
        </>
      )}
      <h3>Copy to your website</h3>
      <pre>{snippet}</pre>
      <button
        onClick={() =>
          job.task(async () => {
            await navigator.clipboard.writeText(snippet);
            setNotice("Public embed code copied.");
          })
        }
      >
        Copy public embed code
      </button>
      <p>
        <a
          href={`/chat.html?assistant=${encodeURIComponent(assistant)}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open shareable chat page
        </a>{" "}
        · <a href="/v1/downloads/wordpress">Download WordPress plugin</a>
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void job.task(async () => {
            setCheck(
              await client.request(root + "/installation-check", {
                method: "POST",
                body: JSON.stringify({
                  url: host,
                  app_origin: location.origin,
                }),
              }),
            );
          });
        }}
      >
        <label>
          Installed website page
          <input
            type="url"
            value={host}
            onChange={(event) => setHost(event.target.value)}
            required
          />
        </label>
        <button disabled={job.busy}>Verify website installation</button>
      </form>
      {check && (
        <div role="status">
          <p>
            Script: {check.script_detected ? "detected" : "not detected"} ·
            Domain: {check.domain_allowed ? "allowed" : "not allowed"} · Public
            chat: {check.public_enabled ? "enabled" : "disabled"}
          </p>
          <p>{String(check.note)}</p>
        </div>
      )}
      <details>
        <summary>Signed customer identity</summary>
        <p>
          Guests can ask questions and contact support. Verified website
          identity is required for booking and private appointment access. Your
          backend signs a short-lived assertion; the signing secret must never
          appear in HTML, browser bundles or WordPress options. See the
          signed-identity example in the repository.
        </p>
        <button
          disabled={job.busy}
          onClick={() =>
            job.task(async () => {
              const result = await client.request<{ secret: string }>(
                root + "/identity-secret",
                { method: "POST" },
              );
              setSecret(result.secret);
              setTick((value) => value + 1);
            })
          }
        >
          Create or rotate identity signing secret
        </button>
        {secret && (
          <>
            <p>
              Shown once. Save on your backend; rotating invalidates existing
              public sessions.
            </p>
            <code>{secret}</code>
            <button onClick={() => setSecret("")}>Hide signing secret</button>
          </>
        )}
      </details>
      <details>
        <summary>React and API integration</summary>
        <pre>{`// Use an application session token, never an AI provider key.\n<AssistantChat assistantId="${assistant}" token={sessionToken} mode="model" />\n\nPOST /v1/public/assistants/${assistant}/sessions\nPOST /v1/assistants/${assistant}/chat`}</pre>
        <p>
          For external sites use the iframe widget. Direct browser API requests
          are same-origin by default; use your own backend proxy for a
          cross-origin custom UI.
        </p>
      </details>
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
