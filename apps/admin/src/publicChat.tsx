import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { streamChat, type ChatResult } from "../../../packages/js-sdk";
import { client, type ChatMessage } from "./model";
import { InlineBooking } from "./features/InlineBooking";
import "./style.css";

type Info = {
  configuration: {
    name: string;
    welcome_message: string;
    color: string;
    font_family?: string;
    suggested_questions: string[];
  };
  project_id: string;
  verified: boolean;
  lead_capture: boolean;
  support_enabled: boolean;
  bookings_enabled: boolean;
  preview?: boolean;
};
const assistant = new URLSearchParams(location.search).get("assistant") || "";
const initial = new URLSearchParams(location.hash.slice(1));
history.replaceState(null, "", location.pathname + location.search);

function PublicChat() {
  const [info, setInfo] = useState<Info>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversation, setConversation] = useState<string>();
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("extractive");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    let active = true;
    async function start() {
      try {
        let data: Info;
        if (initial.get("session")) {
          client.token = initial.get("session")!;
          data = await client.request<Info>(
            `/v1/assistants/${assistant}/widget-info`,
          );
        } else {
          const result = await client.request<Info & { access_token: string }>(
            `/v1/public/assistants/${assistant}/sessions`,
            {
              method: "POST",
              body: JSON.stringify({
                identity_token: initial.get("identity") || "",
              }),
            },
          );
          client.token = result.access_token;
          data = result;
        }
        const provider = await client.request<{ status: string }>(
          `/v1/assistants/${assistant}/provider/status`,
        );
        if (active) {
          setInfo(data);
          setMode(
            ["available", "configured"].includes(provider.status)
              ? "model"
              : "extractive",
          );
        }
      } catch (failure) {
        if (active)
          setError(
            failure instanceof Error
              ? failure.message
              : "Chat could not start.",
          );
      }
    }
    if (assistant) void start();
    else setError("Assistant ID is missing.");
    return () => {
      active = false;
      controller.current?.abort();
    };
  }, []);
  async function send(text: string) {
    if (!text.trim() || busy || !info) return;
    setInput("");
    setBusy(true);
    setError("");
    setMessages((old) => [
      ...old,
      { role: "user", text },
      { role: "assistant", text: "", provisional: true },
    ]);
    controller.current = new AbortController();
    let complete = false;
    try {
      for await (const event of streamChat(
        client,
        assistant,
        { text, mode, conversation_id: conversation },
        controller.current.signal,
      )) {
        if (event.type === "token")
          setMessages((old) =>
            old.map((message, index) =>
              index === old.length - 1
                ? { ...message, text: message.text + String(event.data.text) }
                : message,
            ),
          );
        if (event.type === "error")
          throw new Error(
            String(event.data.code).replaceAll("_", " ").toLowerCase(),
          );
        if (event.type === "result") {
          const result = event.data as unknown as ChatResult;
          setConversation(result.conversation_id);
          setMessages((old) =>
            old.map((message, index) =>
              index === old.length - 1
                ? {
                    role: "assistant",
                    text: result.text,
                    citations: result.citations,
                    action: result.action,
                  }
                : message,
            ),
          );
          complete = true;
        }
      }
      if (!complete) throw new Error("Response interrupted. Please retry.");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Request failed.");
    } finally {
      if (!complete)
        setMessages((old) => old.filter((message) => !message.provisional));
      setBusy(false);
    }
  }
  return (
    <main
      className="public-chat"
      style={
        info
          ? ({
              "--green": info.configuration.color,
              fontFamily: info.configuration.font_family || "system-ui",
            } as React.CSSProperties)
          : undefined
      }
    >
      <header>
        <h1>{info?.configuration.name || "Business assistant"}</h1>
        {info?.preview && (
          <strong>Private draft preview · expires in 10 minutes</strong>
        )}
      </header>
      {info && <p>{info.configuration.welcome_message}</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {!info && !error && <p>Starting secure chat…</p>}
      <div className="public-messages" role="log" aria-live="polite">
        {messages.map((message, index) => (
          <article key={index} className="panel">
            <strong>
              {message.role === "user" ? "You" : "Assistant"}
              {message.provisional ? " · provisional" : ""}
            </strong>
            <p style={{ whiteSpace: "pre-wrap" }}>{message.text}</p>
            {message.citations?.map((citation) => (
              <details key={citation.chunk_id}>
                <summary>
                  {citation.title} · page {citation.page}
                </summary>
                <p>{citation.text}</p>
              </details>
            ))}
            {message.action &&
              (info?.verified && !info.preview ? (
                <InlineBooking action={message.action} />
              ) : (
                <p>
                  Use this business's verified sign-in integration to book or
                  access appointments.
                </p>
              ))}
          </article>
        ))}
      </div>
      {info && (
        <>
          {!messages.length && (
            <div className="button-row">
              {info.configuration.suggested_questions.map((question) => (
                <button
                  key={question}
                  disabled={busy}
                  onClick={() => void send(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void send(input);
            }}
          >
            <label>
              Your question
              <input
                aria-label="Your question"
                maxLength={4000}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                disabled={busy}
                required
              />
            </label>
            <div className="button-row">
              <select
                aria-label="Answer mode"
                value={mode}
                disabled={busy}
                onChange={(event) => setMode(event.target.value)}
              >
                <option value="extractive">Source passages</option>
                <option value="model">AI answers</option>
              </select>
              <button className="primary" disabled={busy || !input.trim()}>
                Send message
              </button>
              {busy && (
                <button
                  type="button"
                  onClick={() => controller.current?.abort()}
                >
                  Stop
                </button>
              )}
            </div>
          </form>
          <div className="button-row">
            <button
              disabled={busy || !conversation}
              onClick={async () => {
                try {
                  await client.request(
                    `/v1/assistants/${assistant}/conversations/${conversation}`,
                    { method: "DELETE" },
                  );
                  setConversation(undefined);
                  setMessages([]);
                  setNotice("Conversation deleted.");
                } catch (failure) {
                  setError(String(failure));
                }
              }}
            >
              Delete this conversation
            </button>
            {!info.preview && info.support_enabled && (
              <button
                disabled={busy || !conversation}
                onClick={async () => {
                  try {
                    await client.request(
                      `/v1/projects/${info.project_id}/tickets`,
                      {
                        method: "POST",
                        body: JSON.stringify({
                          conversation_id: conversation,
                          subject: "Website visitor requested support",
                        }),
                      },
                    );
                    setNotice(
                      "Your conversation is in the human support queue. Response time is not guaranteed.",
                    );
                  } catch (failure) {
                    setError(String(failure));
                  }
                }}
              >
                Request human support
              </button>
            )}
            <button
              disabled={busy || !conversation}
              onClick={async () => {
                try {
                  const result = await client.request<{ items: ChatMessage[] }>(
                    `/v1/assistants/${assistant}/conversations/${conversation}`,
                  );
                  setMessages(result.items);
                } catch (failure) {
                  setError(String(failure));
                }
              }}
            >
              Refresh replies
            </button>
          </div>
          {info.lead_capture && !info.preview && (
            <details>
              <summary>Leave an enquiry</summary>
              <form
                onSubmit={async (event) => {
                  event.preventDefault();
                  const form = event.currentTarget;
                  const fields = new FormData(form);
                  try {
                    await client.request(`/v1/assistants/${assistant}/leads`, {
                      method: "POST",
                      body: JSON.stringify({
                        name: fields.get("name"),
                        email: fields.get("email"),
                        message: fields.get("message"),
                        consent: fields.get("consent") === "on",
                      }),
                    });
                    form.reset();
                    setNotice("Your enquiry was received.");
                  } catch (failure) {
                    setError(String(failure));
                  }
                }}
              >
                <label>
                  Name
                  <input name="name" required maxLength={100} />
                </label>
                <label>
                  Email
                  <input type="email" name="email" required maxLength={254} />
                </label>
                <label>
                  Enquiry
                  <textarea name="message" required maxLength={2000} />
                </label>
                <label>
                  <input type="checkbox" name="consent" required /> I agree to
                  share these details with this business for a response.
                </label>
                <button>Submit enquiry</button>
              </form>
            </details>
          )}
          <p className="fine">
            AI answers can be wrong. Check the cited information. Sessions
            expire; reloading starts a new anonymous conversation unless the
            host provides verified identity.
          </p>
        </>
      )}
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<PublicChat />);
