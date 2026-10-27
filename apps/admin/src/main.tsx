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
import { Settings } from "./features/Settings";
import { Support } from "./features/Support";
import { Privacy } from "./features/Privacy";
import { Analytics } from "./features/Analytics";
import { Workflows } from "./features/Workflows";
import { Calendars } from "./features/Calendars";
import { Team, Join } from "./features/Team";
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
  if (location.hash.startsWith("#invite=")) return <Join />;
  if (!token) return <LoginScreen studio={studio} />;
  const role = projects.find((p) => p.id === project)?.role ?? "end_user";
  const writer = ["owner", "administrator", "developer"].includes(role);
  const current = assistants.find((a) => a.id === assistant);
  return (
    <div
      className={widget ? "layout widget" : "layout"}
      style={
        studio.branding
          ? ({ "--green": studio.branding.color } as React.CSSProperties)
          : undefined
      }
    >
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
              onChange={(e) =>
                e.target.value === "__new__"
                  ? void studio.createOrganization()
                  : setProject(e.target.value)
              }
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
              <option value="__new__">＋ New organisation</option>
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
              "Settings",
              "Support",
              "Workflows",
              "Privacy",
              "Analytics",
              "Team",
              "Calendars",
            ]
              .filter((name) => {
                if (
                  [
                    "Settings",
                    "Calendars",
                    "Workflows",
                    "Tools",
                    "Integrate",
                    "Knowledge",
                  ].includes(name)
                )
                  return writer;
                if (name === "Team")
                  return ["owner", "administrator"].includes(role);
                if (name === "Analytics")
                  return [
                    "owner",
                    "administrator",
                    "analyst",
                    "support_agent",
                  ].includes(role);
                return true;
              })
              .map((name, i) => (
                <button
                  key={name}
                  className={tab === name ? "nav active" : "nav"}
                  onClick={() => {
                    setTab(name);
                    setError("");
                  }}
                >
                  <span aria-hidden="true">
                    {
                      ["◫", "▤", "◌", "▦", "⌘", "↗", "⚙", "☏", "⇢", "◇", "▥"][
                        i
                      ]
                    }
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
            <button onClick={() => setTab("Support")}>Support</button>
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
            <span className="badge">Self-hosted workspace</span>
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
        {assistant && tab === "Settings" && (
          <Settings
            key={assistant}
            assistant={assistant}
            onChanged={() => void studio.refreshBranding()}
          />
        )}
        {project && tab === "Support" && (
          <Support key={project} project={project} />
        )}
        {project && tab === "Workflows" && (
          <Workflows key={project} project={project} />
        )}
        {project && tab === "Privacy" && (
          <Privacy
            key={project}
            project={project}
            onErased={() => {
              studio.setMessages([]);
              studio.setConversation(undefined);
              studio.setBookings([]);
              studio.setOperation(null);
              studio.setSource(null);
              studio.setResults([]);
            }}
          />
        )}
        {project && tab === "Analytics" && (
          <Analytics key={project} project={project} />
        )}
        {project && tab === "Team" && <Team key={project} project={project} />}
        {project && tab === "Calendars" && (
          <Calendars
            key={project}
            project={project}
            onChanged={() => void studio.refreshServices()}
          />
        )}
        <footer>
          <span>◈ &nbsp; Assistant Studio</span>
          <span>Local first. Evidence always.</span>
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
