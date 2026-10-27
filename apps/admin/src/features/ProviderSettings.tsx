import { useEffect, useState } from "react";
import { client } from "../model";
import { ErrorNotice, useResource, useTask } from "./shared";

type Provider = { id: string; name: string; base_url: string };
type Configuration = {
  provider: string;
  model: string;
  base_url: string;
  max_tokens: number;
  token_parameter: string;
  has_key: boolean;
  revision: number;
  inherited: boolean;
  can_manage: boolean;
};

export function ProviderSettings({
  assistant,
  onChanged,
}: {
  assistant: string;
  onChanged: () => void;
}) {
  const root = `/v1/assistants/${assistant}/provider`;
  const [tick, setTick] = useState(0);
  const saved = useResource<Configuration>(root, tick);
  const catalog = useResource<{
    items: Provider[];
    custom_endpoints: string[];
  }>("/v1/providers");
  const [draft, setDraft] = useState<Configuration>();
  const [key, setKey] = useState("");
  const [consent, setConsent] = useState(false);
  const [result, setResult] = useState("");
  const job = useTask();
  useEffect(() => {
    setDraft(saved.data);
    setKey("");
    setConsent(
      Boolean(
        saved.data &&
          saved.data.revision > 0 &&
          saved.data.provider !== "ollama",
      ),
    );
  }, [saved.data]);
  if (!draft || !catalog.data)
    return <ErrorNotice error={saved.error || catalog.error} />;
  const disabled = job.busy || !draft.can_manage;
  async function save() {
    if (!draft) return;
    setResult("");
    await job.task(async () => {
      await client.request(root, {
        method: "PUT",
        body: JSON.stringify({
          revision: draft.revision,
          provider: draft.provider,
          model: draft.model,
          base_url: draft.provider === "ollama" ? "" : draft.base_url,
          api_key: key || null,
          max_tokens: draft.max_tokens,
          token_parameter: draft.token_parameter,
          allow_external: consent,
        }),
      });
      setKey("");
      setTick((value) => value + 1);
      setResult(
        "Provider saved. Test the saved connection before using AI answers.",
      );
      onChanged();
    });
  }
  return (
    <section className="panel">
      <h2>AI provider</h2>
      <p className="muted">
        Choose the service for this assistant. API keys stay on the server and
        are excluded from assistant exports. Embeddings remain a separate local
        setting.
      </p>
      <ErrorNotice error={job.error || saved.error} />
      {!draft.can_manage && (
        <p>
          Only workspace owners and administrators can change provider
          credentials.
        </p>
      )}
      <div className="form-grid">
        <label>
          Provider
          <select
            aria-label="AI provider"
            disabled={disabled}
            value={draft.provider}
            onChange={(e) => {
              const provider = e.target.value;
              setDraft({
                ...draft,
                provider,
                has_key: false,
                model: "",
                base_url:
                  catalog.data!.items.find((item) => item.id === provider)
                    ?.base_url || "",
                token_parameter:
                  provider === "openai"
                    ? "max_completion_tokens"
                    : "max_tokens",
              });
              setKey("");
              setConsent(false);
              setResult("");
            }}
          >
            {catalog.data.items.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Model ID
          <input
            aria-label="Provider model ID"
            value={draft.model}
            disabled={disabled}
            placeholder="Exact model ID from your provider account"
            onChange={(e) => setDraft({ ...draft, model: e.target.value })}
          />
        </label>
        {draft.provider === "custom" && (
          <>
            <label>
              Approved endpoint
              <select
                aria-label="Provider endpoint"
                value={draft.base_url}
                disabled={disabled}
                onChange={(e) =>
                  setDraft({ ...draft, base_url: e.target.value })
                }
              >
                <option value="">Choose an approved endpoint</option>
                {catalog.data.custom_endpoints.map((url) => (
                  <option key={url}>{url}</option>
                ))}
              </select>
            </label>
            <label>
              Output token parameter
              <select
                value={draft.token_parameter}
                disabled={disabled}
                onChange={(e) =>
                  setDraft({ ...draft, token_parameter: e.target.value })
                }
              >
                <option>max_tokens</option>
                <option>max_completion_tokens</option>
              </select>
            </label>
            {!catalog.data.custom_endpoints.length && (
              <p>
                The server operator must approve your endpoint with
                AI_CUSTOM_BASE_URLS first.
              </p>
            )}
          </>
        )}
        {draft.provider !== "ollama" && (
          <>
            <label>
              API key
              <input
                aria-label="Provider API key"
                type="password"
                autoComplete="new-password"
                value={key}
                disabled={disabled}
                placeholder={
                  draft.has_key && !draft.inherited
                    ? "Stored securely; leave blank to keep the same provider key"
                    : "Enter this assistant's API key"
                }
                onChange={(e) => setKey(e.target.value)}
              />
            </label>
            <label>
              Maximum output tokens
              <input
                type="number"
                min={256}
                max={8192}
                value={draft.max_tokens}
                disabled={disabled}
                onChange={(e) =>
                  setDraft({ ...draft, max_tokens: Number(e.target.value) })
                }
              />
            </label>
          </>
        )}
      </div>
      {draft.provider !== "ollama" && (
        <label>
          <input
            type="checkbox"
            checked={consent}
            disabled={disabled}
            onChange={(e) => setConsent(e.target.checked)}
          />{" "}
          Allow this service to receive questions, relevant source excerpts and
          conversation context. Provider charges may apply.
        </label>
      )}
      <p className="fine">
        {draft.inherited
          ? "Using the deployment default. Save a separate key to override it for this assistant."
          : "Assistant override active. These operational credentials are separate from published content versions."}
      </p>
      <div className="button-row">
        <button disabled={disabled} onClick={save}>
          Save AI provider
        </button>
        <button
          disabled={disabled}
          onClick={() =>
            job.task(async () => {
              setResult("");
              await client.request(root + "/test", { method: "POST" });
              setResult(
                "Saved connection passed a small real completion request.",
              );
              onChanged();
            })
          }
        >
          Test saved provider
        </button>
        <button
          disabled={disabled || draft.inherited}
          onClick={() =>
            job.task(async () => {
              await client.request(root + `?revision=${draft.revision}`, {
                method: "DELETE",
              });
              setTick((value) => value + 1);
              setKey("");
              setResult("Deployment default restored.");
              onChanged();
            })
          }
        >
          Use deployment default
        </button>
      </div>
      {result && <p role="status">{result}</p>}
    </section>
  );
}
