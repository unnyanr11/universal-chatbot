import { useRef, useState } from "react";
import { client } from "../model";
import { ErrorNotice, useResource, useTask } from "./shared";
type Node = {
  type: string;
  key?: string;
  label?: string;
  value_type?: string;
  arguments?: Record<string, string | number | boolean>;
  equals?: string | number | boolean;
  target?: number;
};
type Definition = { name: string; nodes: Node[] };
type Workflow = {
  id: string;
  name: string;
  versions: { number: number; definition: Definition }[];
};
type Run = {
  id: string;
  state: string;
  revision: number;
  dry_run: boolean;
  cursor: number;
  lease_until?: number;
  next: Node | null;
  trace: { node: number; type: string; state: string; error?: string }[];
  approval?: {
    preview?: {
      service: string;
      start_at: string;
      timezone: string;
      location: string;
    };
    policy: string;
    state: string;
  };
};
const template: Definition = {
  name: "Book a consultation",
  nodes: [
    {
      type: "collect",
      key: "slot",
      label: "Choose an available slot",
      value_type: "string",
    },
    {
      type: "propose_booking",
      key: "proposal",
      arguments: { slot_id: "$slot" },
    },
    {
      type: "confirmation",
      key: "result",
      label: "Review and confirm booking",
    },
    { type: "end" },
  ],
};
const types = [
  "collect",
  "validate",
  "branch",
  "knowledge",
  "services",
  "slots",
  "propose_booking",
  "confirmation",
  "end",
];
export function Workflows({ project }: { project: string }) {
  const editor = useRef<HTMLElement | null>(null);
  const root = `/v1/projects/${project}`;
  const [tick, setTick] = useState(0),
    [draft, setDraft] = useState<Definition>(structuredClone(template)),
    [selected, setSelected] = useState(""),
    [version, setVersion] = useState(1),
    [dry, setDry] = useState(true),
    [run, setRun] = useState<Run>(),
    [value, setValue] = useState(""),
    [service, setService] = useState("");
  const { data, error } = useResource<{ items: Workflow[] }>(
    root + "/workflows",
    tick,
  );
  const runs = useResource<{ items: Run[] }>(root + "/workflow-runs", tick);
  const services = useResource<{ items: { id: string; name: string }[] }>(
    root + "/services",
  );
  const slots = useResource<{
    items: { slot_id: string; start_at: string; timezone: string }[];
  }>(service ? root + `/services/${service}/slots` : "", tick);
  const job = useTask();
  function nodeChange(index: number, patch: Partial<Node>) {
    setDraft((old) => ({
      ...old,
      nodes: old.nodes.map((n, i) => (i === index ? { ...n, ...patch } : n)),
    }));
  }
  async function save() {
    if (
      editor.current &&
      !Array.from(editor.current.querySelectorAll("textarea")).every((input) =>
        input.reportValidity(),
      )
    )
      return;
    await job.task(async () => {
      if (selected) {
        const result = await client.request<{ version: number }>(
          root + `/workflows/${selected}/versions`,
          { method: "POST", body: JSON.stringify(draft) },
        );
        setVersion(result.version);
      } else {
        const result = await client.request<{ id: string; version: number }>(
          root + "/workflows",
          { method: "POST", body: JSON.stringify(draft) },
        );
        setSelected(result.id);
        setVersion(result.version);
      }
      setTick((v) => v + 1);
    });
  }
  async function resume(approve = false) {
    if (!run) return;
    await job.task(async () => {
      let input: string | number | boolean = value;
      if (run.next?.value_type === "integer") input = Number(value);
      if (run.next?.value_type === "boolean") input = value === "true";
      const result = await client.request<Run>(
        root + `/workflow-runs/${run.id}/resume`,
        {
          method: "POST",
          body: JSON.stringify({
            revision: run.revision,
            ...(approve ? { approve: true } : { value: input }),
          }),
        },
      );
      setRun(result);
      setValue("");
      setTick((v) => v + 1);
    });
  }
  return (
    <>
      <ErrorNotice error={job.error || error} />
      <div className="booking-grid">
        <section className="panel" ref={editor}>
          <h2>Workflow builder</h2>
          <p className="muted">
            A bounded sequence of validated steps. Forward branches are
            supported; arbitrary code, HTTP and loops are disabled.
          </p>
          <label>
            Saved workflow
            <select
              value={selected}
              onChange={(e) => {
                setSelected(e.target.value);
                const workflow = data?.items.find(
                  (w) => w.id === e.target.value,
                );
                if (workflow) {
                  const latest = workflow.versions.at(-1)!;
                  setDraft(latest.definition);
                  setVersion(latest.number);
                } else {
                  setDraft(structuredClone(template));
                  setVersion(1);
                }
              }}
            >
              <option value="">New workflow</option>
              {data?.items.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Workflow name
            <input
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </label>
          {draft.nodes.map((node, index) => (
            <article className="workflow-node" key={index}>
              <div className="section-heading">
                <strong>Step {index + 1}</strong>
                <div>
                  <button
                    aria-label={`Move step ${index + 1} up`}
                    disabled={index === 0}
                    onClick={() => {
                      const nodes = [...draft.nodes];
                      [nodes[index - 1], nodes[index]] = [
                        nodes[index],
                        nodes[index - 1],
                      ];
                      setDraft({ ...draft, nodes });
                    }}
                  >
                    ↑
                  </button>
                  <button
                    aria-label={`Remove step ${index + 1}`}
                    onClick={() =>
                      setDraft({
                        ...draft,
                        nodes: draft.nodes.filter((_, i) => i !== index),
                      })
                    }
                  >
                    ×
                  </button>
                </div>
              </div>
              <label>
                Step type
                <select
                  value={node.type}
                  onChange={(e) => nodeChange(index, { type: e.target.value })}
                >
                  {types.map((type) => (
                    <option key={type}>{type}</option>
                  ))}
                </select>
              </label>
              {node.type !== "end" && (
                <>
                  <label>
                    Variable key
                    <input
                      value={node.key ?? "input"}
                      onChange={(e) =>
                        nodeChange(index, { key: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Label
                    <input
                      value={node.label ?? ""}
                      onChange={(e) =>
                        nodeChange(index, { label: e.target.value })
                      }
                    />
                  </label>
                </>
              )}
              {node.type === "collect" && (
                <label>
                  Input type
                  <select
                    value={node.value_type ?? "string"}
                    onChange={(e) =>
                      nodeChange(index, { value_type: e.target.value })
                    }
                  >
                    <option>string</option>
                    <option>integer</option>
                    <option>boolean</option>
                  </select>
                </label>
              )}
              {["services", "slots", "knowledge", "propose_booking"].includes(
                node.type,
              ) && (
                <label>
                  Arguments (JSON; use $variable for mappings)
                  <textarea
                    defaultValue={JSON.stringify(node.arguments ?? {})}
                    key={selected + node.type + index}
                    onBlur={(e) => {
                      try {
                        nodeChange(index, {
                          arguments: JSON.parse(e.target.value),
                        });
                      } catch {
                        e.target.setCustomValidity("Use valid JSON");
                        e.target.reportValidity();
                      }
                    }}
                    onChange={(e) => e.target.setCustomValidity("")}
                  />
                </label>
              )}
              {["branch", "validate"].includes(node.type) && (
                <label>
                  Equals
                  <input
                    value={String(node.equals ?? "")}
                    onChange={(e) =>
                      nodeChange(index, { equals: e.target.value })
                    }
                  />
                </label>
              )}
              {node.type === "branch" && (
                <label>
                  Target step index (zero based)
                  <input
                    type="number"
                    value={node.target ?? 0}
                    onChange={(e) =>
                      nodeChange(index, { target: Number(e.target.value) })
                    }
                  />
                </label>
              )}
            </article>
          ))}
          <div className="button-row">
            <button
              onClick={() =>
                setDraft({
                  ...draft,
                  nodes: [
                    ...draft.nodes.slice(0, -1),
                    {
                      type: "collect",
                      key: "field" + draft.nodes.length,
                      label: "New input",
                    },
                    ...draft.nodes.slice(-1),
                  ],
                })
              }
            >
              Add step before end
            </button>
            <button className="primary" disabled={job.busy} onClick={save}>
              {selected ? "Save new version" : "Save workflow"}
            </button>
          </div>
          <details>
            <summary>Validated JSON source</summary>
            <pre>{JSON.stringify(draft, null, 2)}</pre>
          </details>
        </section>
        <section className="panel">
          <h2>Run and inspect</h2>
          <p className="muted">
            Runs are pinned to a saved definition. Each step is a durable
            checkpoint; previews never reserve slots.
          </p>
          <label>
            Version
            <input
              type="number"
              min={1}
              value={version}
              onChange={(e) => setVersion(Number(e.target.value))}
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={dry}
              onChange={(e) => setDry(e.target.checked)}
            />
            Dry run — no booking actions are created
          </label>
          <button
            className="primary"
            disabled={!selected || job.busy}
            onClick={() =>
              job.task(async () => {
                setRun(
                  await client.request<Run>(
                    root + `/workflows/${selected}/runs`,
                    {
                      method: "POST",
                      body: JSON.stringify({
                        version,
                        dry_run: dry,
                        idempotency_key: crypto.randomUUID(),
                      }),
                    },
                  ),
                );
                setTick((v) => v + 1);
              })
            }
          >
            Start {dry ? "dry run" : "live run"}
          </button>
          {run && (
            <article className="receipt">
              <h3>
                {run.dry_run
                  ? "DRY RUN · SIMULATED WRITES"
                  : "LIVE LOCAL WORKFLOW"}
              </h3>
              <span className="badge">{run.state.replaceAll("_", " ")}</span>
              <p className="fine">
                Run {run.id} · Revision {run.revision}
              </p>
              {run.state === "waiting" && run.next?.type === "collect" && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void resume();
                  }}
                >
                  <h3>{run.next.label || run.next.key}</h3>
                  {run.next.key === "slot" ? (
                    <>
                      <label>
                        Service
                        <select
                          aria-label="Service"
                          value={service}
                          onChange={(e) => setService(e.target.value)}
                        >
                          <option value="">Choose service</option>
                          {services.data?.items.map((s) => (
                            <option value={s.id} key={s.id}>
                              {s.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Available slot
                        <select
                          aria-label="Available slot"
                          value={value}
                          required
                          onChange={(e) => setValue(e.target.value)}
                        >
                          <option value="">Choose slot</option>
                          {slots.data?.items.map((s) => (
                            <option value={s.slot_id} key={s.slot_id}>
                              {new Date(s.start_at).toLocaleString()} ·{" "}
                              {s.timezone}
                            </option>
                          ))}
                        </select>
                      </label>
                    </>
                  ) : (
                    <label>
                      Input value
                      <input
                        value={value}
                        required
                        onChange={(e) => setValue(e.target.value)}
                      />
                    </label>
                  )}
                  <button disabled={job.busy}>Continue workflow</button>
                </form>
              )}
              {run.state === "awaiting_confirmation" && (
                <>
                  <h3>Review required action</h3>
                  {run.approval?.preview ? (
                    <>
                      <strong>{run.approval.preview.service}</strong>
                      <p>
                        {new Intl.DateTimeFormat(undefined, {
                          dateStyle: "medium",
                          timeStyle: "short",
                          timeZone: run.approval.preview.timezone,
                        }).format(new Date(run.approval.preview.start_at))}{" "}
                        · {run.approval.preview.timezone}
                      </p>
                      <p>{run.approval.preview.location}</p>
                      <p className="fine">{run.approval.policy}</p>
                    </>
                  ) : (
                    <p>Dry run: confirmation records the simulation only.</p>
                  )}
                  <button
                    className="primary"
                    disabled={job.busy}
                    onClick={() => resume(true)}
                  >
                    {run.dry_run
                      ? "Confirm simulation"
                      : "Approve exact booking"}
                  </button>
                </>
              )}
              {["waiting", "awaiting_confirmation"].includes(run.state) && (
                <button
                  disabled={job.busy}
                  onClick={() =>
                    job.task(async () => {
                      setRun(
                        await client.request<Run>(
                          root + `/workflow-runs/${run.id}/cancel`,
                          {
                            method: "POST",
                            body: JSON.stringify({ revision: run.revision }),
                          },
                        ),
                      );
                      setTick((v) => v + 1);
                    })
                  }
                >
                  Cancel run
                </button>
              )}
              {run.state === "running" && (
                <>
                  <p className="muted">
                    Interrupted or active run. Recovery is available after its
                    lease expires.
                  </p>
                  <button
                    disabled={job.busy}
                    onClick={() =>
                      job.task(async () => {
                        setRun(
                          await client.request<Run>(
                            root + `/workflow-runs/${run.id}/resume`,
                            {
                              method: "POST",
                              body: JSON.stringify({
                                revision: run.revision,
                                recover: true,
                              }),
                            },
                          ),
                        );
                        setTick((v) => v + 1);
                      })
                    }
                  >
                    Recover interrupted run
                  </button>
                </>
              )}
              <h3>Execution trace</h3>
              {run.trace.map((step, i) => (
                <p className="passage" key={i}>
                  Step {step.node + 1} · {step.type} · {step.state}
                  {step.error && <span className="error">{step.error}</span>}
                </p>
              ))}
            </article>
          )}
          <h3>Saved runs</h3>
          {runs.data?.items.map((r) => (
            <button
              className="ticket-choice"
              key={r.id}
              onClick={() => setRun(r)}
            >
              <strong>
                {r.id.slice(0, 8)} · {r.dry_run ? "dry run" : "live"}
              </strong>
              <span className="badge">{r.state}</span>
            </button>
          ))}
        </section>
      </div>
    </>
  );
}
