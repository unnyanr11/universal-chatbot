import { type StudioState } from "../useStudio";
import { client, localTime, widget, type Assistant } from "../model";
import { type Citation } from "../../../../packages/js-sdk/index";
export function LoginScreen({ studio }: { studio: StudioState }) {
  const {
    email,
    setEmail,
    password,
    setPassword,
    assistant,
    error,
    busy,
    conversation,
    login,
  } = studio;
  const current = studio.assistants.find((a) => a.id === studio.assistant);
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
          ● &nbsp; Local first · No paid API required
        </div>
      </div>
      <form className="login-form" onSubmit={login}>
        <span className="eyebrow">WELCOME TO YOUR WORKSPACE</span>
        <h2>Sign in to Studio</h2>
        <p className="muted">
          Use an account created by your local seed command.
        </p>
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button className="primary" disabled={busy}>
          {busy ? "Signing in…" : "Open workspace →"}
        </button>
        <p className="fine">
          Development preview · Synthetic sample businesses
          <br />
          Tokens stay in memory. Reloading requires sign-in.
        </p>
      </form>
    </main>
  );
}
