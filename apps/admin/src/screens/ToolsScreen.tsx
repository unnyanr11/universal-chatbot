import { useState } from "react";
import { type StudioState } from "../useStudio";
import { client } from "../model";
export function ToolsScreen({ studio }: { studio: StudioState }) {
  const { tools, action, busy, api } = studio;
  const [name, setName] = useState("list_services"),
    [argumentsText, setArgumentsText] = useState("{}"),
    [dry, setDry] = useState(true),
    [result, setResult] = useState<unknown>();
  return (
    <>
      <section className="panel">
        <h2>Connected capabilities</h2>
        <p className="muted">
          Only allowlisted server-owned handlers are enabled. Tool arguments and
          outputs are schema-validated. No arbitrary HTTP, SQL or code execution
          is available.
        </p>
        {tools.map((t) => (
          <article className="tool-contract" key={t.name}>
            <div className="tool-row">
              <span className="file-icon">⌘</span>
              <div className="grow">
                <strong>{t.name}</strong>
                <small>
                  {t.description ??
                    (t.kind === "write"
                      ? "Requires explicit confirmation"
                      : "Read only")}
                </small>
              </div>
              <span className="badge">{t.status}</span>
            </div>
            {t.input_schema && (
              <details>
                <summary>Input and output contracts</summary>
                <pre>
                  {JSON.stringify(
                    { input: t.input_schema, output: t.output_schema },
                    null,
                    2,
                  )}
                </pre>
              </details>
            )}
          </article>
        ))}
      </section>
      <section className="panel">
        <h2>Tool sandbox</h2>
        <p className="muted">
          Read results come from the real local service. Dry-run writes validate
          input and preview context without creating an operation. Turning dry
          run off still creates a proposal; it does not confirm a booking.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action(async () =>
              setResult(
                await client.request(api("/tool-calls"), {
                  method: "POST",
                  body: JSON.stringify({
                    name,
                    arguments: JSON.parse(argumentsText),
                    dry_run: dry,
                    idempotency_key: crypto.randomUUID(),
                  }),
                }),
              ),
            );
          }}
        >
          <label>
            Tool
            <select
              aria-label="Sandbox tool"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setResult(undefined);
              }}
            >
              {tools
                .filter((t) => t.input_schema)
                .map((t) => (
                  <option key={t.name}>{t.name}</option>
                ))}
            </select>
          </label>
          <label>
            Arguments (JSON)
            <textarea
              value={argumentsText}
              onChange={(e) => setArgumentsText(e.target.value)}
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={dry}
              onChange={(e) => setDry(e.target.checked)}
            />
            Dry run writes (no booking operation created)
          </label>
          <button disabled={busy}>Run sandbox check</button>
        </form>
        {result !== undefined && (
          <pre aria-label="Tool result">{JSON.stringify(result, null, 2)}</pre>
        )}
      </section>
    </>
  );
}
