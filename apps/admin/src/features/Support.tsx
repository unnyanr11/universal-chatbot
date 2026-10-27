import { useState } from "react";
import { client } from "../model";
import { ErrorNotice, useResource, useTask } from "./shared";
type Ticket = {
  id: string;
  subject: string;
  state: string;
  version: number;
  assigned_to: string;
  conversation_id: string;
};
type Detail = Ticket & {
  messages: { role: string; text: string }[];
  notes?: { text: string; author_id: string }[];
};
export function Support({ project }: { project: string }) {
  const root = `/v1/projects/${project}`;
  const [tick, setTick] = useState(0),
    [selected, setSelected] = useState(""),
    [text, setText] = useState(""),
    [internal, setInternal] = useState(false);
  const { data, error } = useResource<{ items: Ticket[] }>(
    root + "/tickets",
    tick,
  );
  const detail = useResource<Detail>(
    selected ? root + "/tickets/" + selected : "",
    tick,
  );
  const job = useTask();
  const ticket = detail.data;
  async function state(action: string) {
    if (!ticket) return;
    await job.task(async () => {
      await client.request(root + `/tickets/${ticket.id}/state`, {
        method: "POST",
        body: JSON.stringify({ action, version: ticket.version }),
      });
      setTick((t) => t + 1);
    });
  }
  return (
    <div className="booking-grid">
      <section className="panel">
        <h2>Human support inbox</h2>
        <p className="muted">
          Agents see their organisation’s queue. Customers see only their own
          requests.
        </p>
        <ErrorNotice error={error || job.error} />
        <button onClick={() => setTick((v) => v + 1)}>Refresh inbox</button>
        {data?.items.length === 0 && (
          <p className="empty">No support requests.</p>
        )}
        {data?.items.map((t) => (
          <button
            className="ticket-choice"
            key={t.id}
            onClick={() => setSelected(t.id)}
          >
            <strong>{t.subject}</strong>
            <span className="badge">{t.state}</span>
            <small>{t.id.slice(0, 8)}</small>
          </button>
        ))}
      </section>
      <section className="panel">
        <ErrorNotice error={detail.error} />
        {ticket ? (
          <>
            <h2>{ticket.subject}</h2>
            <span className="badge">{ticket.state}</span>
            <div className="button-row">
              <button disabled={job.busy} onClick={() => state("claim")}>
                Claim conversation
              </button>
              <button disabled={job.busy} onClick={() => state("resume")}>
                Return to assistant
              </button>
              <button disabled={job.busy} onClick={() => state("resolve")}>
                Resolve ticket
              </button>
            </div>
            <div className="ticket-messages">
              {ticket.messages.map((m, i) => (
                <article className={"message " + m.role} key={i}>
                  <small>{m.role.toUpperCase()}</small>
                  <p>{m.text}</p>
                </article>
              ))}
            </div>
            {ticket.notes && (
              <>
                <h3>Private agent notes</h3>
                {ticket.notes.map((n, i) => (
                  <p className="passage" key={i}>
                    {n.text}
                  </p>
                ))}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void job.task(async () => {
                      await client.request(
                        root + `/tickets/${ticket.id}/messages`,
                        {
                          method: "POST",
                          body: JSON.stringify({ text, internal }),
                        },
                      );
                      setText("");
                      setTick((v) => v + 1);
                    });
                  }}
                >
                  <label>
                    Reply or note
                    <textarea
                      value={text}
                      maxLength={4000}
                      required
                      onChange={(e) => setText(e.target.value)}
                    />
                  </label>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={internal}
                      onChange={(e) => setInternal(e.target.checked)}
                    />
                    Internal note (never shown to customer)
                  </label>
                  <button
                    className="primary"
                    disabled={job.busy || ticket.state !== "assigned"}
                  >
                    {internal ? "Save private note" : "Send human reply"}
                  </button>
                </form>
              </>
            )}
          </>
        ) : (
          <div className="empty">
            Select a conversation to inspect its messages.
          </div>
        )}
      </section>
    </div>
  );
}
