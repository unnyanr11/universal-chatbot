import { useState } from "react";
import { client } from "../model";
import { ErrorNotice, useResource, useTask } from "./shared";
export function Team({ project }: { project: string }) {
  const root = `/v1/projects/${project}`;
  const [tick, setTick] = useState(0),
    [email, setEmail] = useState(""),
    [role, setRole] = useState("end_user"),
    [link, setLink] = useState("");
  const { data, error } = useResource<{
    items: { user_id: string; email: string; role: string }[];
  }>(root + "/members", tick);
  const job = useTask();
  return (
    <section className="panel">
      <h2>Organisation members</h2>
      <p className="muted">
        Roles apply to this organisation’s projects. Removing a member revokes
        their sessions and cancels pending approvals. The last owner cannot be
        removed.
      </p>
      <ErrorNotice error={error || job.error} />
      {data?.items.map((m) => (
        <article className="tool-row" key={m.user_id}>
          <div className="grow">
            <strong>{m.email}</strong>
            <small>{m.role}</small>
          </div>
          <button
            disabled={job.busy}
            onClick={() => {
              if (!confirm("Remove this member and revoke their sessions?"))
                return;
              void job.task(async () => {
                await client.request(root + "/members/" + m.user_id, {
                  method: "DELETE",
                });
                setTick((v) => v + 1);
              });
            }}
          >
            Remove member
          </button>
        </article>
      ))}
      <h3>Create an invitation</h3>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void job.task(async () => {
            const result = await client.request<{ token: string }>(
              root + "/invitations",
              { method: "POST", body: JSON.stringify({ email, role }) },
            );
            setLink(
              location.origin + "/#invite=" + encodeURIComponent(result.token),
            );
          });
        }}
      >
        <label>
          Invite email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Role
          <select
            aria-label="Invitation role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            {[
              "end_user",
              "analyst",
              "support_agent",
              "developer",
              "administrator",
              "owner",
            ].map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <button disabled={job.busy}>Create local invitation link</button>
      </form>
      {link && (
        <div className="passage">
          <p>
            No email has been sent. This one-time link expires in 24 hours.
            Share it only through an authorised channel.
          </p>
          <input aria-label="Invitation link" value={link} readOnly />
          <button onClick={() => navigator.clipboard.writeText(link)}>
            Copy link
          </button>
        </div>
      )}
    </section>
  );
}
export function Join() {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [existing, setExisting] = useState(false),
    [joined, setJoined] = useState(false);
  const job = useTask();
  const token = new URLSearchParams(location.hash.slice(1)).get("invite");
  return (
    <main className="login-form">
      <h1>Join a workspace</h1>
      <p className="muted">
        This invitation link grants its specified role. Use the email address
        named in the invitation.
      </p>
      <ErrorNotice error={job.error} />
      {joined ? (
        <>
          <p>Membership created. Sign in to open the workspace.</p>
          <a href="/">Go to sign in →</a>
        </>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void job.task(async () => {
              if (existing) {
                const login = await client.request<{ access_token: string }>(
                  "/v1/sessions",
                  { method: "POST", body: JSON.stringify({ email, password }) },
                );
                const previous = client.token;
                try {
                  client.token = login.access_token;
                  await client.request("/v1/invitations/accept", {
                    method: "POST",
                    body: JSON.stringify({ token }),
                  });
                  await client.request("/v1/sessions/current", {
                    method: "DELETE",
                  });
                } finally {
                  client.token = previous;
                }
              } else {
                await client.request("/v1/invitations/register", {
                  method: "POST",
                  body: JSON.stringify({ token, email, password }),
                });
              }
              history.replaceState(null, "", "/");
              setPassword("");
              setJoined(true);
            });
          }}
        >
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              minLength={existing ? 1 : 16}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={existing ? "current-password" : "new-password"}
              required
            />
          </label>
          <label className="check-label">
            <input
              type="checkbox"
              checked={existing}
              onChange={(e) => setExisting(e.target.checked)}
            />
            I already have an account
          </label>
          <button className="primary" disabled={job.busy}>
            Accept invitation
          </button>
        </form>
      )}
    </main>
  );
}
