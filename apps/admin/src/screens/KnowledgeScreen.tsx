import { type StudioState } from "../useStudio";
import { client, localTime, widget, type Assistant } from "../model";
import { type Citation } from "../../../../packages/js-sdk/index";
export function KnowledgeScreen({ studio }: { studio: StudioState }) {
  const {
    assistant,
    error,
    setNotice,
    busy,
    docs,
    service,
    setMessages,
    source,
    setSource,
    debugQuery,
    setDebugQuery,
    results,
    setResults,
    bot,
    action,
    refreshDocs,
  } = studio;
  const { retrieval, setRetrieval } = studio;
  return (
    <>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Approved knowledge</h2>
            <p className="muted">
              TXT, Markdown, CSV, DOCX and text PDFs · Up to 2 MB · No OCR
            </p>
          </div>
          <label className="upload">
            ＋ Add source
            <input
              aria-label="Upload source"
              disabled={busy || !assistant}
              type="file"
              accept=".txt,.md,.pdf,.csv,.docx"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                void action(async () => {
                  const data = new FormData();
                  data.append("file", file);
                  await client.request(bot("/documents"), {
                    method: "POST",
                    body: data,
                  });
                  await refreshDocs();
                  setNotice(
                    "Source uploaded. We’re preparing it for answers. It will show Ready when processing finishes.",
                  );
                });
                e.target.value = "";
              }}
            />
          </label>
        </div>
        {docs.length === 0 ? (
          <div className="empty">
            ▤<h3>Your assistant is ready to learn</h3>
            <p>Add service details, business hours or your FAQ.</p>
          </div>
        ) : (
          <div className="source-list">
            {docs.map((d) => (
              <article key={d.id}>
                <div className="file-icon">▤</div>
                <div className="grow">
                  <strong>{d.title}</strong>
                  <small>
                    {d.error || "Private to this assistant’s workspace"}
                  </small>
                </div>
                <span className={"badge " + d.status}>{d.status}</span>
                <button
                  disabled={busy}
                  onClick={() => {
                    if (
                      !confirm(
                        "Remove this source and redact answers citing it?",
                      )
                    )
                      return;
                    void action(async () => {
                      await client.request(bot("/documents/" + d.id), {
                        method: "DELETE",
                      });
                      await refreshDocs();
                      setMessages([]);
                      setSource(null);
                      setResults([]);
                    });
                  }}
                >
                  Remove
                </button>
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="panel">
        <h2>Retrieval debugger</h2>
        <select
          aria-label="Debug retrieval method"
          value={retrieval}
          onChange={(e) => setRetrieval(e.target.value)}
        >
          <option value="lexical">Lexical</option>
          <option value="semantic">Semantic (local embeddings required)</option>
          <option value="hybrid">Hybrid (local embeddings required)</option>
        </select>
        <p className="muted">
          Lexical ranking scores describe search relevance, not answer
          confidence.
        </p>
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            void action(async () =>
              setResults(
                (
                  await client.request<{
                    items: (Citation & { score: number })[];
                  }>(
                    bot(
                      "/search?q=" +
                        encodeURIComponent(debugQuery) +
                        "&method=" +
                        retrieval,
                    ),
                  )
                ).items,
              ),
            );
          }}
        >
          <input
            aria-label="Search knowledge"
            value={debugQuery}
            onChange={(e) => setDebugQuery(e.target.value)}
            placeholder="Search your sources…"
            required
          />
          <button disabled={busy}>Search passages</button>
        </form>
        {results.map((r) => (
          <article className="passage" key={r.chunk_id}>
            <strong>
              {r.title} · page {r.page}
            </strong>
            <span className="badge">Score {r.score}</span>
            <p>{r.text}</p>
          </article>
        ))}
      </section>
    </>
  );
}
