import { useEffect, useState } from "react";
import { client } from "../model";
import { ErrorNotice, useResource, useTask, downloadJson } from "./shared";
type Config = {
  name: string;
  welcome_message: string;
  description: string;
  color: string;
  font_family?: string;
  tone: string;
  timezone: string;
  languages: string[];
  suggested_questions: string[];
  allowed_domains: string[];
};
type Settings = {
  revision: number;
  published_version: number;
  configuration: Config;
};
type Version = {
  number: number;
  published_at: number;
  manifest: { configuration: Config };
};
export function Settings({
  assistant,
  onChanged,
}: {
  assistant: string;
  onChanged?: () => void;
}) {
  const root = `/v1/assistants/${assistant}`;
  const [tick, setTick] = useState(0),
    [draft, setDraft] = useState<Config>();
  const { data, error } = useResource<Settings>(root + "/configuration", tick);
  const versions = useResource<{ items: Version[] }>(root + "/versions", tick);
  const job = useTask();
  useEffect(() => {
    setDraft(data?.configuration);
    if (data) onChanged?.();
  }, [data]);
  async function save() {
    if (!draft || !data) return;
    await job.task(async () => {
      await client.request(root + "/configuration", {
        method: "PUT",
        body: JSON.stringify({ revision: data.revision, configuration: draft }),
      });
      setTick((v) => v + 1);
    });
  }
  if (!draft || !data) return <ErrorNotice error={error} />;
  return (
    <section className="panel">
      <h2>Assistant configuration</h2>
      <p className="muted">
        Save drafts, publish a source manifest, or restore a previous published
        version. Deleted sources stay deleted.
      </p>
      <ErrorNotice error={job.error || error} />
      <div className="form-grid">
        <label>
          Name
          <input
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
        </label>
        <label>
          Timezone
          <input
            value={draft.timezone}
            onChange={(e) => setDraft({ ...draft, timezone: e.target.value })}
          />
        </label>
        <label>
          Welcome message
          <input
            value={draft.welcome_message}
            onChange={(e) =>
              setDraft({ ...draft, welcome_message: e.target.value })
            }
          />
        </label>
        <label>
          Tone
          <select
            value={draft.tone}
            onChange={(e) => setDraft({ ...draft, tone: e.target.value })}
          >
            <option>friendly</option>
            <option>formal</option>
            <option>concise</option>
          </select>
        </label>
        <label>
          Description
          <textarea
            value={draft.description}
            onChange={(e) =>
              setDraft({ ...draft, description: e.target.value })
            }
          />
        </label>
        <label>
          Brand color
          <input
            type="color"
            value={draft.color}
            onChange={(e) => setDraft({ ...draft, color: e.target.value })}
          />
        </label>
        <label>
          Font family
          <select
            value={draft.font_family || "system-ui"}
            onChange={(event) =>
              setDraft({ ...draft, font_family: event.target.value })
            }
          >
            <option>system-ui</option>
            <option>arial</option>
            <option>georgia</option>
            <option>verdana</option>
          </select>
        </label>
        <label>
          Suggested questions (one per line)
          <textarea
            value={draft.suggested_questions.join("\n")}
            onChange={(e) =>
              setDraft({
                ...draft,
                suggested_questions: e.target.value.split("\n").filter(Boolean),
              })
            }
          />
        </label>
        <label>
          Allowed embedding host names
          <textarea
            value={draft.allowed_domains.join("\n")}
            onChange={(e) =>
              setDraft({
                ...draft,
                allowed_domains: e.target.value.split("\n").filter(Boolean),
              })
            }
          />
        </label>
      </div>
      <div className="button-row">
        <button disabled={job.busy} onClick={save}>
          Save draft
        </button>
        <button
          className="primary"
          disabled={job.busy || data.revision === 0}
          onClick={() =>
            job.task(async () => {
              await client.request(root + "/publish", {
                method: "POST",
                body: JSON.stringify({ revision: data.revision }),
              });
              setTick((v) => v + 1);
            })
          }
        >
          Publish saved draft
        </button>
        <button
          onClick={() => downloadJson("assistant-configuration.json", draft)}
        >
          Export configuration
        </button>
        <label className="upload">
          Import draft
          <input
            type="file"
            accept=".json"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file)
                void job.task(async () => {
                  if (file.size > 50000)
                    throw new Error("Configuration exceeds 50 KB");
                  await client.request(root + "/configuration", {
                    method: "PUT",
                    body: JSON.stringify({
                      revision: data.revision,
                      configuration: JSON.parse(await file.text()),
                    }),
                  });
                  setTick((v) => v + 1);
                });
            }}
          />
        </label>
      </div>
      <p className="fine">
        Revision {data.revision} · Published version{" "}
        {data.published_version || "none"} · Local preview only; publish does
        not deploy externally.
      </p>
      <h3>Version history</h3>
      {versions.data?.items.map((v) => (
        <article className="tool-row" key={v.number}>
          <div className="grow">
            <strong>
              Version {v.number} · {v.manifest.configuration.name}
            </strong>
            <small>{new Date(v.published_at * 1000).toLocaleString()}</small>
          </div>
          <button
            disabled={job.busy}
            onClick={() =>
              job.task(async () => {
                await client.request(root + `/versions/${v.number}/restore`, {
                  method: "POST",
                  body: JSON.stringify({ revision: data.revision }),
                });
                setTick((t) => t + 1);
              })
            }
          >
            Restore version {v.number}
          </button>
        </article>
      ))}
    </section>
  );
}
