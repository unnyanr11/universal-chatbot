import { type StudioState } from "../useStudio";
export function OverviewScreen({ studio }: { studio: StudioState }) {
  const { setTab, docs, bookings, mode } = studio;
  const writer = ["owner", "administrator", "developer"].includes(
    studio.projects.find((project) => project.id === studio.project)?.role ??
      "",
  );
  return (
    <>
      <section className="hero">
        <div>
          <span className="eyebrow">YOUR ASSISTANT, YOUR BUSINESS</span>
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
          <button
            className="primary"
            onClick={() => setTab(writer ? "Get started" : "Chat")}
          >
            {writer ? "Set up your assistant →" : "Start a conversation →"}
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
            {docs.filter((d) => d.status === "ready").length} ready to answer
            questions
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
          <strong className="word">
            {mode !== "extractive" ? "Configured AI" : "Source passages"}
          </strong>
          <small>
            {mode !== "extractive"
              ? "Answers grounded in your sources"
              : "Answers use the text from your sources"}
          </small>
        </article>
      </div>
      {writer && (
        <section className="panel">
          <div className="section-heading">
            <h2>Your next steps</h2>
            <span className="muted">Set up once, improve as you go</span>
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
                "Inspect passages and test your configured AI.",
                "Chat",
              ],
              [
                "03",
                "Share your assistant",
                "Publish when ready and add chat to your website.",
                "Integrate",
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
      )}
    </>
  );
}
