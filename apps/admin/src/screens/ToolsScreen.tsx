import { type StudioState } from "../useStudio";
import { client, localTime, widget, type Assistant } from "../model";
import { type Citation } from "../../../../packages/js-sdk/index";
export function ToolsScreen({ studio }: { studio: StudioState }) {
  const { tools } = studio;
  return (
    <section className="panel">
      <h2>Connected capabilities</h2>
      <p className="muted">
        Only server-owned local booking operations are enabled. Generated text
        cannot execute arbitrary code or HTTP requests.
      </p>
      {tools.map((t) => (
        <article className="tool-row" key={t.name}>
          <span className="file-icon">⌘</span>
          <div className="grow">
            <strong>{t.name}</strong>
            <small>
              {t.kind === "write"
                ? "Requires explicit confirmation"
                : "Read only"}
            </small>
          </div>
          <span className="badge">{t.status}</span>
        </article>
      ))}
    </section>
  );
}
