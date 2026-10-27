import { useState } from "react";
import { client } from "../model";
import { ErrorNotice, useResource, useTask } from "./shared";

type Review = {
  id: string;
  title: string;
  text: string;
  color: string;
  font_family: string;
};
export function Onboarding({
  assistant,
  onChanged,
}: {
  assistant: string;
  onChanged: () => void;
}) {
  const root = `/v1/assistants/${assistant}`;
  const templates = useResource<{
    items: { id: string; name: string; description: string }[];
  }>("/v1/assistant-templates");
  const [template, setTemplate] = useState("faq");
  const [url, setUrl] = useState("");
  const [review, setReview] = useState<Review>();
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState("");
  const task = useTask();
  return (
    <section className="panel">
      <h2>Guided onboarding</h2>
      <p>
        Start with a template, add approved information, test privately, then
        publish and install. Appointments, enquiries and human support can be
        added when needed.
      </p>
      <ErrorNotice error={task.error || templates.error} />
      <label>
        Starter template
        <select
          value={template}
          onChange={(event) => setTemplate(event.target.value)}
        >
          {templates.data?.items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <p className="fine">
        {
          templates.data?.items.find((item) => item.id === template)
            ?.description
        }{" "}
        Templates change the draft; they do not invent business facts, staff or
        available appointments.
      </p>
      <button
        disabled={task.busy}
        onClick={() =>
          task.task(async () => {
            const config = await client.request<{ revision: number }>(
              root + "/configuration",
            );
            await client.request(root + "/template", {
              method: "POST",
              body: JSON.stringify({ template, revision: config.revision }),
            });
            setNotice(
              "Template saved as a draft. Review it in Settings before publishing.",
            );
            onChanged();
          })
        }
      >
        Apply starter template
      </button>
      <h3>Import an approved website page</h3>
      <p>
        Enter one public HTTPS page at a time. Review its extracted text before
        approval. JavaScript-rendered content, private sites and automatic
        whole-site crawling are not imported.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void task.task(async () => {
            setNotice("");
            setReview(
              await client.request<Review>(root + "/website-review", {
                method: "POST",
                body: JSON.stringify({ url }),
              }),
            );
          });
        }}
      >
        <label>
          Website page URL
          <input
            type="url"
            value={url}
            placeholder="https://your-business.example/about"
            onChange={(event) => setUrl(event.target.value)}
            required
          />
        </label>
        <button disabled={task.busy}>Fetch page for review</button>
      </form>
      {review && (
        <div>
          <h4>{review.title}</h4>
          <label>
            Extracted text for review
            <textarea
              aria-label="Extracted website text"
              readOnly
              value={review.text}
              rows={10}
            />
          </label>
          <p>
            Suggested colour: {review.color} · font: {review.font_family}.
            Suggestions are not applied automatically.
          </p>
          <div className="button-row">
            <button
              disabled={task.busy}
              onClick={() =>
                task.task(async () => {
                  await client.request(root + "/website-import", {
                    method: "POST",
                    body: JSON.stringify({
                      review_id: review.id,
                      accepted: true,
                    }),
                  });
                  setReview(undefined);
                  setNotice(
                    "Approved page queued for indexing. Publish after it becomes ready.",
                  );
                  onChanged();
                })
              }
            >
              Approve website import
            </button>
            <button
              disabled={task.busy}
              onClick={() =>
                task.task(async () => {
                  const config = await client.request<{
                    revision: number;
                    configuration: Record<string, unknown>;
                  }>(root + "/configuration");
                  await client.request(root + "/configuration", {
                    method: "PUT",
                    body: JSON.stringify({
                      revision: config.revision,
                      configuration: {
                        ...config.configuration,
                        color: review.color,
                        font_family: review.font_family,
                      },
                    }),
                  });
                  setNotice(
                    "Suggested styling saved to the draft. Publish to apply it publicly.",
                  );
                  onChanged();
                })
              }
            >
              Use suggested styling in draft
            </button>
            <button onClick={() => setReview(undefined)}>Discard review</button>
          </div>
        </div>
      )}
      <h3>Private staging preview</h3>
      <p>
        Test draft configuration and unpublished knowledge using an isolated
        10-minute session. Real bookings, enquiries and handoffs are disabled in
        preview.
      </p>
      <button
        disabled={task.busy}
        onClick={() =>
          task.task(async () => {
            const result = await client.request<{ access_token: string }>(
              root + "/preview",
              { method: "POST" },
            );
            setPreview(
              `${location.origin}/chat.html?assistant=${encodeURIComponent(assistant)}#session=${encodeURIComponent(result.access_token)}`,
            );
          })
        }
      >
        Create private draft preview
      </button>
      {preview && (
        <p>
          <a href={preview} target="_blank" rel="noopener noreferrer">
            Open private draft preview
          </a>
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
