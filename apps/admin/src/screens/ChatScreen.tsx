import { type StudioState } from "../useStudio";
import { client, localTime, widget, type Assistant } from "../model";
import { type Citation } from "../../../../packages/js-sdk/index";
export function ChatScreen({ studio }: { studio: StudioState }) {
  const {
    assistant,
    setTab,
    busy,
    services,
    service,
    messages,
    question,
    setQuestion,
    mode,
    setMode,
    source,
    setSource,
    controller,
    chatEnd,
    bot,
    action,
    send,
    clearChat,
  } = studio;
  const current = studio.assistants.find((a) => a.id === studio.assistant);
  return (
    <div className="chat-layout">
      <section className="chat panel">
        <div className="chat-toolbar">
          <span>
            <i className="online" /> {current?.name ?? "Choose an assistant"}
          </span>
          <select
            aria-label="Answer mode"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="extractive">Source passages · no AI</option>
            <option value="local">Local model · Ollama required</option>
          </select>
          <button disabled={busy} onClick={clearChat}>
            Clear
          </button>
        </div>
        <div className="messages" aria-live="polite">
          {messages.length === 0 && (
            <div className="chat-welcome">
              <div className="assistant-icon">◈</div>
              <h2>What would you like to know?</h2>
              <p>
                Ask about the information in your approved sources,
                <br />
                or browse services to book an appointment.
              </p>
              <div className="suggestions">
                <button
                  onClick={() => setQuestion("What services do you offer?")}
                >
                  What services do you offer? ↗
                </button>
                <button onClick={() => setTab("Appointments")}>
                  Book an appointment ↗
                </button>
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <article className={"message " + m.role} key={i}>
              <small>
                {m.role === "user"
                  ? "YOU"
                  : mode === "extractive"
                    ? "SOURCE PASSAGES"
                    : "AI ANSWER · CHECK SOURCES"}
              </small>
              <p>{m.text}</p>
              {m.citations?.map((c, n) => (
                <button
                  className="citation"
                  key={c.chunk_id}
                  onClick={() =>
                    action(async () =>
                      setSource(
                        await client.request<Citation>(
                          bot("/sources/" + c.chunk_id),
                        ),
                      ),
                    )
                  }
                >
                  [{n + 1}] {c.title} · p. {c.page}
                </button>
              ))}
            </article>
          ))}
          {busy && (
            <div className="muted" role="status">
              Working…
            </div>
          )}
          <div ref={chatEnd} />
        </div>
        <form className="composer" onSubmit={send}>
          <input
            aria-label="Message"
            placeholder="Ask your assistant…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={4000}
            disabled={busy}
          />
          {busy ? (
            <button type="button" onClick={() => controller.current?.abort()}>
              Stop
            </button>
          ) : (
            <button
              className="primary"
              disabled={!question.trim() || !assistant}
              aria-label="Send message"
            >
              ↑
            </button>
          )}
        </form>
        <p className="fine chat-note">
          {mode === "extractive"
            ? "Passages are quoted from retrieved sources."
            : "AI-generated answers may be incorrect. Check the sources."}{" "}
          No action runs from generated text.
        </p>
      </section>
      {!widget && (
        <aside className="panel chat-side">
          <span className="eyebrow">EVIDENCE & ACTIONS</span>
          <h3>Keep answers accountable.</h3>
          <p className="muted">
            Select a citation to inspect its exact source passage.
          </p>
          {source && (
            <article className="passage">
              <strong>
                {source.title} · page {source.page}
              </strong>
              <p>{source.text}</p>
            </article>
          )}
          <hr />
          <h3>Ready to take action?</h3>
          <p className="muted">
            Availability comes from the local booking service. Every write needs
            your confirmation.
          </p>
          <button onClick={() => setTab("Appointments")}>
            Browse appointments →
          </button>
        </aside>
      )}
    </div>
  );
}
