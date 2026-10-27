import React from "react";
import { createRoot } from "react-dom/client";
import { useStudio } from "./useStudio";
import { client, widget, type Assistant } from "./model";
import "./style.css";
import { LoginScreen } from "./screens/LoginScreen";
import { OverviewScreen } from "./screens/OverviewScreen";
import { KnowledgeScreen } from "./screens/KnowledgeScreen";
import { ChatScreen } from "./screens/ChatScreen";
import { AppointmentsScreen } from "./screens/AppointmentsScreen";
import { ToolsScreen } from "./screens/ToolsScreen";
import { IntegrateScreen } from "./screens/IntegrateScreen";
function App() {
  const studio = useStudio();
  const {
    token,
    setToken,
    projects,
    project,
    setProject,
    assistants,
    setAssistants,
    assistant,
    setAssistant,
    tab,
    setTab,
    error,
    setError,
    notice,
    provider,
    api,
    action,
  } = studio;
  if (!token) return <LoginScreen studio={studio} />;
  const current = assistants.find((a) => a.id === assistant);
  return (
    <div className={widget ? "layout widget" : "layout"}>
      {!widget && (
        <aside className="sidebar">
          <div className="brand">
            ◈ &nbsp; Studio<span className="version">LOCAL</span>
          </div>
          <div className="workspace">
            <span className="eyebrow">WORKSPACE</span>
            <select
              aria-label="Project"
              value={project}
              onChange={(e) => setProject(e.target.value)}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <nav>
            {[
              "Overview",
              "Knowledge",
              "Chat",
              "Appointments",
              "Tools",
              "Integrate",
            ].map((name, i) => (
              <button
                key={name}
                className={tab === name ? "nav active" : "nav"}
                onClick={() => {
                  setTab(name);
                  setError("");
                }}
              >
                <span aria-hidden="true">
                  {["◫", "▤", "◌", "▦", "⌘", "↗"][i]}
                </span>
                {name}
              </button>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="provider">
              <i />
              Local workspace<small>Ollama: {provider}</small>
            </div>
            <button
              className="text-button"
              onClick={() =>
                action(async () => {
                  await client.request("/v1/sessions/current", {
                    method: "DELETE",
                  });
                  client.token = "";
                  setToken("");
                  setProject("");
                  setAssistant("");
                })
              }
            >
              Sign out ↗
            </button>
          </div>
        </aside>
      )}
      <main className="main">
        {widget && (
          <nav aria-label="Widget navigation">
            <button onClick={() => setTab("Chat")}>Chat</button>
            <button onClick={() => setTab("Appointments")}>Appointments</button>
          </nav>
        )}
        <header>
          <div>
            <span className="eyebrow">
              {widget ? "ASSISTANT" : "YOUR ASSISTANT WORKSPACE"}
            </span>
            <h1>{widget ? (current?.name ?? "Assistant") : tab}</h1>
          </div>
          <div className="header-right">
            <span className="badge">Development preview</span>
            <select
              aria-label="Assistant"
              value={assistant}
              onChange={(e) => setAssistant(e.target.value)}
            >
              {assistants.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
        </header>
        {error && (
          <div role="alert" className="error">
            {error}
            <button aria-label="Dismiss error" onClick={() => setError("")}>
              ×
            </button>
          </div>
        )}
        {notice && (
          <div role="status" className="notice">
            {notice}
          </div>
        )}
        {!assistant && (
          <section className="panel">
            <h2>Create your first assistant</h2>
            <button
              onClick={() =>
                action(async () => {
                  const name = prompt("Assistant name");
                  if (!name?.trim()) return;
                  const a = await client.request<Assistant>(
                    api("/assistants"),
                    { method: "POST", body: JSON.stringify({ name }) },
                  );
                  setAssistants((old) => [...old, a]);
                  setAssistant(a.id);
                })
              }
            >
              Create assistant
            </button>
          </section>
        )}
        {tab === "Overview" && <OverviewScreen studio={studio} />}
        {tab === "Knowledge" && <KnowledgeScreen studio={studio} />}
        {tab === "Chat" && <ChatScreen studio={studio} />}
        {tab === "Appointments" && <AppointmentsScreen studio={studio} />}
        {tab === "Tools" && <ToolsScreen studio={studio} />}
        {tab === "Integrate" && <IntegrateScreen studio={studio} />}
        <footer>
          <span>◈ &nbsp; Assistant Studio</span>
          <span>Local first. Evidence always.</span>
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
