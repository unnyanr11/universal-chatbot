import { useEffect, useState } from "react";
import { type StudioState } from "../useStudio";
import { client, widget } from "../model";
import { useResource, useTask } from "../features/shared";

export function LoginScreen({ studio }: { studio: StudioState }) {
  const registration = useResource<{ enabled: boolean }>(
    widget ? "" : "/v1/registration",
  );
  const [signingUp, setSigningUp] = useState(false);
  const [workspace, setWorkspace] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [notice, setNotice] = useState("");
  const signup = useTask();
  useEffect(() => {
    const returned = new URLSearchParams(location.hash.slice(1));
    if (returned.has("access_token") || returned.has("error_description")) {
      // Confirmation still requires a server-verified sign-in. Don't retain URL tokens.
      history.replaceState(null, "", location.pathname + location.search);
      setNotice(
        "Confirmation link received. Sign in below to continue. If confirmation failed, request a new email by creating your account again.",
      );
    }
  }, []);
  const { email, setEmail, password, setPassword, error, busy, login } = studio;
  return (
    <main className="login">
      <div className="login-art">
        <div className="brand">◈ &nbsp; Assistant Studio</div>
        <span className="eyebrow">YOUR KNOWLEDGE. YOUR INFRASTRUCTURE.</span>
        <h1>
          A helpful assistant,
          <br />
          built around
          <br />
          <em>your business.</em>
        </h1>
        <p>
          Bring your sources together. Answer with evidence. Turn a conversation
          into a confirmed appointment.
        </p>
        <div className="local-pill">
          ● &nbsp; Your workspace · Your documents · Your AI account
        </div>
      </div>
      <form
        className="login-form"
        onSubmit={
          signingUp
            ? (event) => {
                event.preventDefault();
                if (password !== confirmation) return;
                void signup.task(async () => {
                  await client.request("/v1/registrations", {
                    method: "POST",
                    body: JSON.stringify({
                      email,
                      password,
                      workspace_name: workspace,
                    }),
                  });
                  setPassword("");
                  setConfirmation("");
                  setSigningUp(false);
                  setNotice(
                    "Check your inbox for a confirmation email. Confirm your email, then return here to sign in. If you already have an account, sign in instead.",
                  );
                });
              }
            : login
        }
      >
        <span className="eyebrow">WELCOME TO YOUR WORKSPACE</span>
        <h2>{signingUp ? "Create your workspace" : "Sign in to Studio"}</h2>
        <p className="muted">
          {signingUp
            ? "Build your own chatbot with private documents and your own AI API key. We’ll email you to confirm your account."
            : "Sign in to manage your assistants, knowledge and website chat."}
        </p>
        {signingUp && (
          <label>
            Workspace name
            <input
              value={workspace}
              onChange={(event) => setWorkspace(event.target.value)}
              maxLength={100}
              required
              placeholder="Your business or project"
            />
          </label>
        )}
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={signingUp ? "new-password" : "current-password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            minLength={signingUp ? 16 : 1}
            maxLength={256}
          />
        </label>
        {signingUp && (
          <>
            <p className="fine">
              Use at least 16 characters. A memorable passphrase works well.
            </p>
            <label>
              Confirm password
              <input
                type="password"
                autoComplete="new-password"
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                required
                minLength={16}
                maxLength={256}
              />
            </label>
            {confirmation && confirmation !== password && (
              <p role="alert" className="error">
                Passwords do not match.
              </p>
            )}
          </>
        )}
        {(error || signup.error) && (
          <p role="alert" className="error">
            {error || signup.error}
          </p>
        )}
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}
        <button
          className="primary"
          disabled={
            busy || signup.busy || (signingUp && password !== confirmation)
          }
        >
          {signingUp
            ? signup.busy
              ? "Creating account…"
              : "Create account →"
            : busy
              ? "Signing in…"
              : "Open workspace →"}
        </button>
        {registration.data?.enabled && (
          <button
            type="button"
            className="text-button"
            disabled={busy || signup.busy}
            onClick={() => {
              setSigningUp(!signingUp);
              studio.setError("");
              setPassword("");
              setConfirmation("");
              setNotice("");
            }}
          >
            {signingUp
              ? "Already have an account? Sign in"
              : "New here? Create a free account"}
          </button>
        )}
        <p className="fine">
          Your workspace · Your business information
          <br />
          Sessions stay in memory. Reloading requires sign-in.
        </p>
      </form>
    </main>
  );
}
