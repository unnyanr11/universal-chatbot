import { useState } from "react";
import { client } from "../model";
import { ErrorNotice, downloadJson, useResource, useTask } from "./shared";
type Memory = { id: string; text: string; expires_at: number; source: string };
export function Privacy({
  project,
  onErased,
}: {
  project: string;
  onErased?: () => void;
}) {
  const [currentPassword, setCurrentPassword] = useState(""),
    [newPassword, setNewPassword] = useState("");
  const root = `/v1/projects/${project}`;
  const [tick, setTick] = useState(0),
    [text, setText] = useState(""),
    [consent, setConsent] = useState(false),
    [confirmation, setConfirmation] = useState("");
  const { data, error } = useResource<{ items: Memory[] }>(
    root + "/memories",
    tick,
  );
  const inbox = useResource<{
    items: {
      id: string;
      service: string;
      start_at: string;
      timezone: string;
    }[];
  }>(root + "/inbox", tick);
  const job = useTask();
  return (
    <>
      <section className="panel">
        <h2>Your preferences and memory</h2>
        <p className="muted">
          Only preferences you explicitly submit are stored. They expire after
          30 days. Never include passwords, payment data or sensitive identity
          information. Local-model answers may use up to three active
          preferences for tone and style. Preferences never grant permissions or
          become factual evidence.
        </p>
        <ErrorNotice error={job.error || error} />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void job.task(async () => {
              await client.request(root + "/memories", {
                method: "POST",
                body: JSON.stringify({ text, consent, retention_days: 30 }),
              });
              setText("");
              setConsent(false);
              setTick((v) => v + 1);
            });
          }}
        >
          <label>
            Preference
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={500}
              required
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            I consent to storing this preference in this workspace.
          </label>
          <button disabled={!consent || job.busy}>Remember preference</button>
        </form>
        {data?.items.map((m) => (
          <article className="tool-row" key={m.id}>
            <div className="grow">
              <strong>{m.text}</strong>
              <small>
                {m.source} · expires{" "}
                {new Date(m.expires_at * 1000).toLocaleDateString()}
              </small>
            </div>
            <button
              disabled={job.busy}
              onClick={() =>
                job.task(async () => {
                  await client.request(root + "/memories/" + m.id, {
                    method: "DELETE",
                  });
                  setTick((v) => v + 1);
                })
              }
            >
              Forget
            </button>
          </article>
        ))}
      </section>
      <section className="panel">
        <h2>In-app notification inbox</h2>
        <button onClick={() => setTick((v) => v + 1)}>
          Refresh notifications
        </button>
        {inbox.data?.items.length === 0 && (
          <p className="muted">
            No delivered reminders. The worker delivers due reminders here.
          </p>
        )}
        {inbox.data?.items.map((n) => (
          <p className="passage" key={n.id}>
            Appointment reminder: {n.service} ·{" "}
            {new Date(n.start_at).toLocaleString()} · business timezone{" "}
            {n.timezone}
          </p>
        ))}
      </section>
      <section className="panel">
        <h2>Change password</h2>
        <p className="muted">
          Changing your password signs out all sessions, including this one.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void job.task(async () => {
              await client.request("/v1/me/password", {
                method: "POST",
                body: JSON.stringify({
                  current_password: currentPassword,
                  new_password: newPassword,
                }),
              });
              setCurrentPassword("");
              setNewPassword("");
              location.reload();
            });
          }}
        >
          <label>
            Current password
            <input
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              maxLength={256}
              required
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </label>
          <label>
            New password
            <input
              type="password"
              autoComplete="new-password"
              value={newPassword}
              minLength={16}
              maxLength={256}
              required
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </label>
          <button disabled={job.busy}>Change password and sign out</button>
        </form>
      </section>
      <section className="panel">
        <h2>Export and delete your workspace data</h2>
        <p className="muted">
          Export includes your conversations, bookings, action receipts,
          workflow runs and preferences. Internal agent notes are excluded.
          Deletion frees your reserved slots and removes those live records.
          Your account, shared business knowledge and existing backups remain.
        </p>
        <button
          disabled={job.busy}
          onClick={() =>
            job.task(async () =>
              downloadJson(
                "my-workspace-data.json",
                await client.request(root + "/my-data"),
              ),
            )
          }
        >
          Export my data
        </button>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void job.task(async () => {
              await client.request(root + "/my-data", {
                method: "DELETE",
                body: JSON.stringify({ confirmation }),
              });
              setConfirmation("");
              setTick((v) => v + 1);
            });
          }}
        >
          <label>
            Type DELETE MY WORKSPACE DATA to confirm
            <input
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
            />
          </label>
          <button
            disabled={job.busy || confirmation !== "DELETE MY WORKSPACE DATA"}
          >
            Delete my workspace data
          </button>
        </form>
        <button
          disabled={job.busy}
          onClick={() =>
            job.task(async () => {
              await client.request("/v1/me/sessions", { method: "DELETE" });
              location.reload();
            })
          }
        >
          Sign out all sessions
        </button>
      </section>
    </>
  );
}
