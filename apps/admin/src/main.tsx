import React from "react";
import { createRoot } from "react-dom/client";
import { useStudio } from "./useStudio";
import { client, widget, type Assistant } from "./model";
import "./style.css";
import { LoginScreen } from "./screens/LoginScreen";
import { OverviewScreen } from "./screens/OverviewScreen";
import { SetupScreen } from "./screens/SetupScreen";
import { KnowledgeScreen } from "./screens/KnowledgeScreen";
import { ChatScreen } from "./screens/ChatScreen";
import { AppointmentsScreen } from "./screens/AppointmentsScreen";
import { ToolsScreen } from "./screens/ToolsScreen";
import { IntegrateScreen } from "./screens/IntegrateScreen";
import { Settings } from "./features/Settings";
import { ProviderSettings } from "./features/ProviderSettings";
import { Support } from "./features/Support";
import { Privacy } from "./features/Privacy";
import { Analytics } from "./features/Analytics";
import { Workflows } from "./features/Workflows";
import { Calendars } from "./features/Calendars";
import { Team, Join } from "./features/Team";
function App() {
  const studio = useStudio();
  const [assistantName, setAssistantName] = React.useState("");
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
          <div className="brand">◈ &nbsp; Studio</div>
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
              "Get started",
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
                    "Get started",
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
              .map((name) => (
                <button
                  key={name}
                  className={tab === name ? "nav active" : "nav"}
                  aria-current={tab === name ? "page" : undefined}
                  onClick={() => {
                    setTab(name);
                    setError("");
                  }}
                >
                  <span aria-hidden="true">
                    {
                      (
                        {
                          Overview: "◫",
                          "Get started": "✓",
                          Knowledge: "▤",
                          Chat: "◌",
                          Appointments: "▦",
                          Tools: "⌘",
                          Integrate: "↗",
                          Settings: "⚙",
                          Support: "☏",
                          Workflows: "⇢",
                          Privacy: "◇",
                          Analytics: "▥",
                          Team: "♧",
                          Calendars: "▦",
                        } as Record<string, string>
                      )[name]
                    }
                  </span>
                  {name}
                </button>
              ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="provider">
              <i />
              AI connection<small>{provider}</small>
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
            {writer && (
              <button
                className="text-button"
                onClick={() => setTab("Get started")}
              >
                Setup guide
              </button>
            )}
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
        {writer && project && !assistant && (
          <section className="panel">
            <h2>Create your first assistant</h2>
            <p>
              Give it a name your customers will recognise. You can change this
              later.
            </p>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void action(async () => {
                  const a = await client.request<Assistant>(
                    api("/assistants"),
                    {
                      method: "POST",
                      body: JSON.stringify({ name: assistantName.trim() }),
                    },
                  );
                  setAssistants((old) => [...old, a]);
                  setAssistant(a.id);
                  setAssistantName("");
                  setTab("Get started");
                });
              }}
            >
              <label>
                Assistant name
                <input
                  value={assistantName}
                  onChange={(event) => setAssistantName(event.target.value)}
                  maxLength={100}
                  placeholder="For example, Acme support"
                  required
                />
              </label>
              <button
                className="primary"
                disabled={studio.busy || !assistantName.trim()}
              >
                Create assistant
              </button>
            </form>
          </section>
        )}
        {tab === "Overview" && <OverviewScreen studio={studio} />}
        {writer && tab === "Get started" && <SetupScreen studio={studio} />}
        {tab === "Knowledge" && <KnowledgeScreen studio={studio} />}
        {tab === "Chat" && <ChatScreen studio={studio} />}
        {tab === "Appointments" && <AppointmentsScreen studio={studio} />}
        {tab === "Tools" && <ToolsScreen studio={studio} />}
        {tab === "Integrate" && <IntegrateScreen studio={studio} />}
        {assistant && tab === "Settings" && (
          <>
            <ProviderSettings
              key={assistant + "-provider"}
              assistant={assistant}
              onChanged={() => void studio.refreshProvider()}
            />
            <Settings
              key={assistant}
              assistant={assistant}
              onChanged={() => void studio.refreshBranding()}
            />
          </>
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
