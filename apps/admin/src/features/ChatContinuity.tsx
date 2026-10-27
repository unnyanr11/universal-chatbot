import { useState } from "react";
import { client, type ChatMessage } from "../model";
import { type StudioState } from "../useStudio";
import { downloadJson, ErrorNotice, useResource, useTask } from "./shared";
export function ChatContinuity({ studio }: { studio: StudioState }) {
  const {
    assistant,
    conversation,
    setConversation,
    setMessages,
    busy,
    messages,
    project,
  } = studio;
  const [tick, setTick] = useState(0);
  const job = useTask();
  const { data, error } = useResource<{
    items: { id: string; created_at: number }[];
  }>(
    assistant ? `/v1/assistants/${assistant}/conversations` : "",
    messages.length + tick,
  );
  async function load(id: string) {
    await job.task(async () => {
      const result = await client.request<{ items: ChatMessage[] }>(
        `/v1/assistants/${assistant}/conversations/${id}`,
      );
      setMessages(result.items);
      setConversation(id);
    });
  }
  async function handoff() {
    await job.task(async () => {
      let id = conversation;
      if (!id) {
        const result = await client.chat(
          assistant,
          "I would like human support",
          undefined,
          "extractive",
        );
        id = result.conversation_id;
        setConversation(id);
      }
      await client.request(`/v1/projects/${project}/tickets`, {
        method: "POST",
        body: JSON.stringify({
          conversation_id: id,
          subject: "Customer requested human support",
        }),
      });
      const result = await client.request<{ items: ChatMessage[] }>(
        `/v1/assistants/${assistant}/conversations/${id}`,
      );
      setMessages([
        ...result.items,
        {
          role: "assistant",
          text: "Human support requested. Automated replies are paused. Response time is not guaranteed.",
          mode: "handoff",
        },
      ]);
      setTick((v) => v + 1);
    });
  }
  return (
    <div className="continuity">
      <div className="button-row">
        <select
          aria-label="Conversation history"
          value={conversation ?? ""}
          disabled={busy || job.busy}
          onChange={(e) => {
            if (e.target.value) void load(e.target.value);
            else {
              setConversation(undefined);
              setMessages([]);
            }
          }}
        >
          <option value="">New conversation</option>
          {data?.items.map((c) => (
            <option value={c.id} key={c.id}>
              {new Date(c.created_at * 1000).toLocaleString()} ·{" "}
              {c.id.slice(0, 6)}
            </option>
          ))}
        </select>
        <button
          disabled={busy || job.busy || !conversation}
          onClick={() => conversation && load(conversation)}
        >
          Refresh replies
        </button>
        <button disabled={busy || job.busy || !assistant} onClick={handoff}>
          Request human support
        </button>
        <button
          disabled={busy || job.busy || !conversation}
          onClick={() =>
            job.task(async () =>
              downloadJson(
                "conversation.json",
                await client.request(
                  `/v1/assistants/${assistant}/conversations/${conversation}`,
                ),
              ),
            )
          }
        >
          Export
        </button>
      </div>
      <ErrorNotice error={error || job.error} />
    </div>
  );
}
