import { useState } from "react";
import { client } from "../model";
import { ErrorNotice, useResource, useTask } from "./shared";
export function IntegrationDiagnostics({ assistant }: { assistant: string }) {
  const [tick, setTick] = useState(0);
  const data = useResource<{
    provider: { status: string };
    documents: Record<string, number>;
    issues: { title: string; fix: string }[];
    next_steps: string[];
    cloud_test_note: string;
  }>(`/v1/assistants/${assistant}/diagnostics`, tick);
  return (
    <section className="panel">
      <h2>Readiness diagnostics</h2>
      <ErrorNotice error={data.error} />
      <button onClick={() => setTick((value) => value + 1)}>
        Refresh readiness diagnostics
      </button>
      {data.data && (
        <>
          <p>
            AI: {data.data.provider.status} · Documents:{" "}
            {data.data.documents.ready || 0} ready,{" "}
            {data.data.documents.queued || 0} queued,{" "}
            {data.data.documents.failed || 0} failed
          </p>
          <p className="fine">{data.data.cloud_test_note}</p>
          {data.data.issues.map((issue, index) => (
            <p key={index}>
              {issue.title}: {issue.fix}
            </p>
          ))}
          <ol>
            {data.data.next_steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
export function Enquiries({ assistant }: { assistant: string }) {
  const [tick, setTick] = useState(0);
  const data = useResource<{
    items: { id: string; name: string; email: string; message: string }[];
  }>(`/v1/assistants/${assistant}/leads`, tick);
  return (
    <section className="panel">
      <h2>Visitor enquiries</h2>
      <ErrorNotice error={data.error} />
      <button onClick={() => setTick((value) => value + 1)}>
        Refresh enquiries
      </button>
      {data.data?.items.map((item) => (
        <article key={item.id}>
          <strong>{item.name}</strong>
          <p>{item.email}</p>
          <p>{item.message}</p>
        </article>
      ))}
      {data.data && !data.data.items.length && <p>No enquiries received.</p>}
    </section>
  );
}
export function WebhookSettings({ project }: { project: string }) {
  const [tick, setTick] = useState(0),
    [url, setUrl] = useState(""),
    [secret, setSecret] = useState("");
  const root = `/v1/projects/${project}/webhooks`;
  const data = useResource<{
    approved_urls: string[];
    items: {
      id: string;
      url: string;
      enabled: boolean;
      deliveries: {
        id: string;
        event: string;
        state: string;
        attempts: number;
        error: string;
      }[];
    }[];
  }>(root, tick);
  const job = useTask();
  return (
    <section className="panel">
      <h2>Signed webhooks</h2>
      <p>
        Deliver lead, support and booking event IDs to approved HTTPS receivers.
        Delivery is at least once; receivers must deduplicate event IDs. No
        contact details or conversation text are sent.
      </p>
      <ErrorNotice error={job.error || data.error} />
      {data.data && (
        <>
          <label>
            Approved receiver
            <select
              value={url}
              onChange={(event) => setUrl(event.target.value)}
            >
              <option value="">Select a receiver</option>
              {data.data.approved_urls.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          {!data.data.approved_urls.length && (
            <p>
              The server operator must approve receiver URLs in
              WEBHOOK_ALLOWED_URLS before enabling delivery.
            </p>
          )}
          <button
            disabled={job.busy || !url}
            onClick={() =>
              job.task(async () => {
                const result = await client.request<{ secret: string }>(root, {
                  method: "POST",
                  body: JSON.stringify({ url }),
                });
                setSecret(result.secret);
                setTick((value) => value + 1);
              })
            }
          >
            Enable webhook receiver
          </button>
          {secret && (
            <>
              <p>Save this receiver signing secret now; it is shown once.</p>
              <code>{secret}</code>
              <button onClick={() => setSecret("")}>Hide webhook secret</button>
            </>
          )}
          {data.data.items.map((endpoint) => (
            <article key={endpoint.id}>
              <h3>{endpoint.url}</h3>
              <p>{endpoint.enabled ? "Enabled" : "Disabled"}</p>
              {endpoint.enabled && (
                <button
                  disabled={job.busy}
                  onClick={() =>
                    job.task(async () => {
                      await client.request(root + "/" + endpoint.id, {
                        method: "DELETE",
                      });
                      setTick((value) => value + 1);
                    })
                  }
                >
                  Disable webhook
                </button>
              )}
              <ul>
                {endpoint.deliveries.map((delivery) => (
                  <li key={delivery.id}>
                    {delivery.event}: {delivery.state} · attempts{" "}
                    {delivery.attempts} {delivery.error}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </>
      )}
    </section>
  );
}
