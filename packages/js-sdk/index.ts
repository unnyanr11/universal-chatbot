/** Application API client. Tokens remain in caller memory; never put privileged keys in bundles. */
export interface Citation {
  chunk_id: string;
  document_id: string;
  title: string;
  page: number;
  text: string;
}
export interface ChatActionReference {
  id: string;
  kind: "book" | "reschedule" | "cancel";
  project_id: string;
  type: "appointment_form";
}
export interface ChatResult {
  action?: ChatActionReference;
  conversation_id: string;
  text: string;
  citations: Citation[];
  mode: string;
  generation_streaming: boolean;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code.replaceAll("_", " ").toLowerCase());
  }
}
export class AssistantClient {
  constructor(
    public token = "",
    public baseUrl = "",
  ) {}
  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    if (this.token) headers.set("Authorization", `Bearer ${this.token}`);
    if (options.body && !(options.body instanceof FormData))
      headers.set("Content-Type", "application/json");
    const response = await fetch(this.baseUrl + path, {
      ...options,
      headers,
      credentials: "omit",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        body.error?.code ?? `HTTP_${response.status}`,
      );
    }
    return response.status === 204 ? (undefined as T) : response.json();
  }
  async chat(
    assistantId: string,
    text: string,
    conversationId: string | undefined,
    mode: string,
    signal?: AbortSignal,
    retrieval = "lexical",
  ) {
    return this.request<ChatResult>(
      `/v1/assistants/${encodeURIComponent(assistantId)}/chat`,
      {
        method: "POST",
        body: JSON.stringify({
          text,
          conversation_id: conversationId,
          mode,
          retrieval,
        }),
        signal,
      },
    );
  }
}

export interface StreamEvent {
  type: string;
  data: Record<string, unknown>;
}
/** SSE over authenticated POST, with cancellation and an incremental UTF-8 decoder. */
export async function* streamChat(
  client: AssistantClient,
  assistantId: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const response = await fetch(
    `${client.baseUrl}/v1/assistants/${encodeURIComponent(assistantId)}/chat`,
    {
      method: "POST",
      credentials: "omit",
      signal,
      headers: {
        Authorization: `Bearer ${client.token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      result.error?.code ?? `HTTP_${response.status}`,
    );
  }
  if (!response.headers.get("content-type")?.includes("text/event-stream")) {
    yield { type: "result", data: await response.json() };
    return;
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Streaming unavailable");
  const decoder = new TextDecoder();
  let pending = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      let boundary: number;
      while ((boundary = pending.indexOf("\n\n")) >= 0) {
        const block = pending.slice(0, boundary);
        pending = pending.slice(boundary + 2);
        const type =
          block
            .split("\n")
            .find((line) => line.startsWith("event: "))
            ?.slice(7) ?? "message";
        const data = block
          .split("\n")
          .filter((line) => line.startsWith("data: "))
          .map((line) => line.slice(6))
          .join("\n");
        if (data) yield { type, data: JSON.parse(data) };
      }
      if (done) break;
    }
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
}
