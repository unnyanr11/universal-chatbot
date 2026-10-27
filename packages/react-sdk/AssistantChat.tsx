import { useEffect, useRef, useState } from "react";
import { AssistantClient, type ChatResult, type Citation } from "../js-sdk";
export interface AssistantChatProps {
  assistantId: string;
  token: string;
  apiBase?: string;
  onCitation?: (citation: Citation) => void;
  onResult?: (result: ChatResult) => void;
}
/** Minimal reusable React integration. The host supplies a short-lived authenticated token. */
export function AssistantChat({
  assistantId,
  token,
  apiBase = "",
  onCitation,
  onResult,
}: AssistantChatProps) {
  const [input, setInput] = useState(""),
    [messages, setMessages] = useState<
      { role: string; text: string; citations?: Citation[] }[]
    >([]),
    [conversation, setConversation] = useState<string>(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    setMessages([]);
    setConversation(undefined);
    return () => controller.current?.abort();
  }, [assistantId, token, apiBase]);
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!input.trim() || busy) return;
    const question = input;
    setInput("");
    setError("");
    setBusy(true);
    setMessages((old) => [...old, { role: "user", text: question }]);
    controller.current = new AbortController();
    try {
      const result = await new AssistantClient(token, apiBase).chat(
        assistantId,
        question,
        conversation,
        "extractive",
        controller.current.signal,
      );
      setConversation(result.conversation_id);
      setMessages((old) => [
        ...old,
        { role: "assistant", text: result.text, citations: result.citations },
      ]);
      onResult?.(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Business assistant">
      <div role="log" aria-live="polite">
        {messages.map((message, index) => (
          <article key={index}>
            <strong>{message.role === "user" ? "You" : "Assistant"}</strong>
            <p style={{ whiteSpace: "pre-wrap" }}>{message.text}</p>
            {message.citations?.map((c) => (
              <button
                type="button"
                key={c.chunk_id}
                onClick={() => onCitation?.(c)}
              >
                {c.title} · page {c.page}
              </button>
            ))}
          </article>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
      <form onSubmit={send}>
        <label>
          Message
          <input
            value={input}
            maxLength={4000}
            disabled={busy}
            onChange={(e) => setInput(e.target.value)}
          />
        </label>
        {busy ? (
          <button type="button" onClick={() => controller.current?.abort()}>
            Stop
          </button>
        ) : (
          <button disabled={!input.trim()}>Send</button>
        )}
      </form>
    </section>
  );
}
