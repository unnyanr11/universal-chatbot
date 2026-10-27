import React, { useEffect, useRef, useState } from "react";
import { type ChatResult, type Citation } from "../../../packages/js-sdk/index";
import {
  client,
  widget,
  type Project,
  type Assistant,
  type Document,
  type Service,
  type Slot,
  type Booking,
  type Operation,
  type Tool,
  type ChatMessage,
} from "./model";
export function useStudio() {
  const [token, setToken] = useState(""),
    [email, setEmail] = useState("owner@cedar.example"),
    [password, setPassword] = useState("");
  const [projects, setProjects] = useState<Project[]>([]),
    [project, setProject] = useState("");
  const [assistants, setAssistants] = useState<Assistant[]>([]),
    [assistant, setAssistant] = useState("");
  const [tab, setTab] = useState(widget ? "Chat" : "Overview"),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [docs, setDocs] = useState<Document[]>([]),
    [services, setServices] = useState<Service[]>([]),
    [bookings, setBookings] = useState<Booking[]>([]),
    [tools, setTools] = useState<Tool[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]),
    [service, setService] = useState(""),
    [operation, setOperation] = useState<Operation | null>(null),
    [reschedule, setReschedule] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]),
    [question, setQuestion] = useState(""),
    [conversation, setConversation] = useState<string>(),
    [mode, setMode] = useState("extractive");
  const [source, setSource] = useState<Citation | null>(null),
    [debugQuery, setDebugQuery] = useState(""),
    [results, setResults] = useState<(Citation & { score: number })[]>([]),
    [provider, setProvider] = useState("checking");
  const controller = useRef<AbortController | null>(null);
  const chatEnd = useRef<HTMLDivElement | null>(null);
  const api = (suffix: string) => `/v1/projects/${project}${suffix}`;
  const bot = (suffix: string) => `/v1/assistants/${assistant}${suffix}`;
  async function action(fn: () => Promise<void>) {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  async function refreshBookings() {
    setBookings(
      (await client.request<{ items: Booking[] }>(api("/bookings"))).items,
    );
  }
  async function refreshDocs() {
    setDocs(
      (await client.request<{ items: Document[] }>(bot("/documents"))).items,
    );
  }
  useEffect(() => {
    client.token = token;
    if (!token) return;
    let active = true;
    client
      .request<{ items: Project[] }>("/v1/projects")
      .then((r) => {
        if (active) {
          setProjects(r.items);
          setProject(r.items[0]?.id ?? "");
        }
      })
      .catch((e) => setError(e.message));
    client
      .request<{ status: string }>("/v1/provider")
      .then((r) => setProvider(r.status))
      .catch(() => setProvider("unavailable"));
    return () => {
      active = false;
    };
  }, [token]);
  useEffect(() => {
    if (!project) return;
    let active = true;
    setAssistant("");
    setOperation(null);
    setReschedule("");
    setService("");
    setSlots([]);
    Promise.all([
      client.request<{ items: Assistant[] }>(api("/assistants")),
      client.request<{ items: Service[] }>(api("/services")),
      client.request<{ items: Booking[] }>(api("/bookings")),
      client.request<{ items: Tool[] }>(api("/tools")),
    ])
      .then(([a, s, b, t]) => {
        if (!active) return;
        setAssistants(a.items);
        const requested = new URLSearchParams(location.search).get("assistant");
        setAssistant(
          a.items.find((x) => x.id === requested)?.id ?? a.items[0]?.id ?? "",
        );
        setServices(s.items);
        setBookings(b.items);
        setTools(t.items);
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
    };
  }, [project]);
  useEffect(() => {
    setMessages([]);
    setConversation(undefined);
    setDocs([]);
    setSource(null);
    setResults([]);
    if (!assistant) return;
    let active = true;
    const load = () =>
      client
        .request<{ items: Document[] }>(bot("/documents"))
        .then((r) => {
          if (active) setDocs(r.items);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    void load();
    const timer = setInterval(load, 4000);
    return () => {
      active = false;
      clearInterval(timer);
      controller.current?.abort();
    };
  }, [assistant]);
  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);
  async function login(e: React.FormEvent) {
    e.preventDefault();
    await action(async () => {
      const r = await client.request<{ access_token: string }>("/v1/sessions", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setPassword("");
      setToken(r.access_token);
    });
  }
  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || !assistant) return;
    const text = question;
    setQuestion("");
    setMessages((m) => [...m, { role: "user", text }]);
    controller.current = new AbortController();
    await action(async () => {
      const r: ChatResult = await client.chat(
        assistant,
        text,
        conversation,
        mode,
        controller.current!.signal,
      );
      setConversation(r.conversation_id);
      setMessages((m) => [
        ...m,
        { role: "assistant", text: r.text, citations: r.citations },
      ]);
    });
  }
  async function chooseService(id: string) {
    setService(id);
    setSlots([]);
    await action(async () =>
      setSlots(
        (await client.request<{ items: Slot[] }>(api(`/services/${id}/slots`)))
          .items,
      ),
    );
  }
  async function propose(kind: string, slotId = "", bookingId = "") {
    await action(async () => {
      const r = await client.request<Operation>(api("/operations"), {
        method: "POST",
        body: JSON.stringify({
          kind,
          slot_id: slotId,
          booking_id: bookingId,
          idempotency_key: crypto.randomUUID(),
        }),
      });
      setOperation(r);
    });
  }
  async function confirmBooking() {
    if (!operation) return;
    await action(async () => {
      const r = await client.request<Operation>(
        api(`/operations/${operation.id}/confirm`),
        { method: "POST" },
      );
      setOperation(r);
      await refreshBookings();
      if (service)
        setSlots(
          (
            await client.request<{ items: Slot[] }>(
              api(`/services/${service}/slots`),
            )
          ).items,
        );
      setReschedule("");
    });
  }
  async function clearChat() {
    await action(async () => {
      if (conversation)
        await client.request(bot(`/conversations/${conversation}`), {
          method: "DELETE",
        });
      setMessages([]);
      setConversation(undefined);
    });
  }
  return {
    token,
    setToken,
    email,
    setEmail,
    password,
    setPassword,
    projects,
    setProjects,
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
    setNotice,
    busy,
    setBusy,
    docs,
    setDocs,
    services,
    setServices,
    bookings,
    setBookings,
    tools,
    setTools,
    slots,
    setSlots,
    service,
    setService,
    operation,
    setOperation,
    reschedule,
    setReschedule,
    messages,
    setMessages,
    question,
    setQuestion,
    conversation,
    setConversation,
    mode,
    setMode,
    source,
    setSource,
    debugQuery,
    setDebugQuery,
    results,
    setResults,
    provider,
    setProvider,
    controller,
    chatEnd,
    api,
    bot,
    action,
    refreshBookings,
    refreshDocs,
    login,
    send,
    chooseService,
    propose,
    confirmBooking,
    clearChat,
  };
}
export type StudioState = ReturnType<typeof useStudio>;
