import { useState } from "react";
import { ErrorNotice, useResource } from "./shared";
type Metrics = {
  conversations: number;
  booking_states: Record<string, number>;
  operation_states: Record<string, number>;
  ticket_states: Record<string, number>;
  definitions: Record<string, string>;
};
export function Analytics({ project }: { project: string }) {
  const [tick, setTick] = useState(0),
    root = `/v1/projects/${project}`;
  const { data, error } = useResource<Metrics>(root + "/analytics", tick);
  const audit = useResource<{
    items: {
      id: string;
      kind: string;
      object_id: string;
      created_at: number;
    }[];
  }>(root + "/audit", tick);
  return (
    <>
      <section className="panel">
        <h2>Measured operations</h2>
        <p className="muted">
          Counts come from stored records. Silence from a customer is not
          counted as resolution.
        </p>
        <ErrorNotice error={error} />
        <button onClick={() => setTick((v) => v + 1)}>Refresh metrics</button>
        {data && (
          <>
            <div className="stats">
              <article>
                <span>Stored conversations</span>
                <strong>{data.conversations}</strong>
                <small>Not a resolution count</small>
              </article>
              <article>
                <span>Confirmed appointments</span>
                <strong>{data.booking_states.confirmed ?? 0}</strong>
                <small>Current authoritative booking state</small>
              </article>
              <article>
                <span>Open support requests</span>
                <strong>
                  {(data.ticket_states.open ?? 0) +
                    (data.ticket_states.assigned ?? 0)}
                </strong>
                <small>Open plus assigned</small>
              </article>
            </div>
            {(
              ["booking_states", "operation_states", "ticket_states"] as const
            ).map((key) => (
              <div key={key}>
                <h3>{key.replaceAll("_", " ")}</h3>
                <div className="button-row">
                  {Object.entries(data[key]).map(([status, count]) => (
                    <span className="badge" key={status}>
                      {status}: {count}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            <p className="fine">
              Model latency, estimated costs and answer accuracy are not
              measured here.
            </p>
          </>
        )}
      </section>
      <section className="panel">
        <h2>Audit trail</h2>
        <ErrorNotice error={audit.error} />
        {audit.data?.items.map((e) => (
          <article className="tool-row" key={e.id}>
            <div className="grow">
              <strong>{e.kind.replaceAll("_", " ")}</strong>
              <small>
                Object {e.object_id} ·{" "}
                {new Date(e.created_at * 1000).toLocaleString()}
              </small>
            </div>
          </article>
        ))}
      </section>
    </>
  );
}
