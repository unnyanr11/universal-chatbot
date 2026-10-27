/** Application API client. Tokens remain in caller memory; never put privileged keys in bundles. */
export interface Citation {
  chunk_id: string;
  document_id: string;
  title: string;
  page: number;
  text: string;
}
export interface ChatResult {
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
  ) {
    return this.request<ChatResult>(
      `/v1/assistants/${encodeURIComponent(assistantId)}/chat`,
      {
        method: "POST",
        body: JSON.stringify({ text, conversation_id: conversationId, mode }),
        signal,
      },
    );
  }
}
