import { type StudioState } from "../useStudio";
import { client, localTime, widget, type Assistant } from "../model";
import { type Citation } from "../../../../packages/js-sdk/index";
export function OverviewScreen({ studio }: { studio: StudioState }) {
  const { setTab, docs, bookings, service, question, mode, source, action } =
    studio;
  return (
    <>
      <section className="hero">
        <div>
          <span className="eyebrow">A PLACE TO START</span>
          <h2>
            Good answers start
            <br />
            with good knowledge.
          </h2>
          <p>
            Add your business information, test an answer,
            <br />
            and see exactly where it comes from.
          </p>
          <button className="primary" onClick={() => setTab("Knowledge")}>
            Manage knowledge ↗
          </button>
        </div>
        <div className="orbit">
          <div className="orbit-inner">◈</div>
          <span className="orbit-tag t1">Approved sources</span>
          <span className="orbit-tag t2">Cited answers</span>
          <span className="orbit-tag t3">Confirmed actions</span>
        </div>
      </section>
      <div className="stats">
        <article>
          <span>Knowledge sources</span>
          <strong>{docs.length}</strong>
          <small>
            {docs.filter((d) => d.status === "ready").length} ready for
            retrieval
          </small>
        </article>
        <article>
          <span>Your appointments</span>
          <strong>
            {bookings.filter((b) => b.status === "confirmed").length}
          </strong>
          <small>Confirmed by the booking service</small>
        </article>
        <article>
          <span>Answer mode</span>
          <strong className="word">Source passages</strong>
          <small>Extractive baseline · No inference needed</small>
        </article>
      </div>
      <section className="panel">
        <div className="section-heading">
          <h2>Your next steps</h2>
          <span className="muted">A working path from source to action</span>
        </div>
        <div className="steps">
          {[
            [
              "01",
              "Add knowledge",
              "Upload a text document or text-based PDF.",
              "Knowledge",
            ],
            [
              "02",
              "Ask a question",
              "Inspect passages and try the local model.",
              "Chat",
            ],
            [
              "03",
              "Make an appointment",
              "Review exact details before confirming.",
              "Appointments",
            ],
          ].map(([n, title, body, destination]) => (
            <button key={n} onClick={() => setTab(destination)}>
              <span>{n}</span>
              <h3>{title} ↗</h3>
              <p>{body}</p>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
