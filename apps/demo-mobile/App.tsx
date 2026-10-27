/** Expo/React Native source example. Requires a device/emulator for acceptance. */
import { useEffect, useRef, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
  ScrollView,
  Text,
  TextInput,
  Button,
  View,
} from "react-native";
import * as SecureStore from "expo-secure-store";
import { AssistantClient, type ChatResult } from "../../packages/js-sdk";
const apiBase = process.env.EXPO_PUBLIC_API_URL ?? "http://10.0.2.2:8000";
const storageKey =
  "assistant-session-" +
  Array.from(apiBase)
    .map((c) => c.charCodeAt(0).toString(16).padStart(4, "0"))
    .join("");
export default function App() {
  const [token, setToken] = useState(""),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [assistant, setAssistant] = useState(""),
    [input, setInput] = useState(""),
    [conversation, setConversation] = useState<string>(),
    [messages, setMessages] = useState<string[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const active = useRef<AbortController | null>(null);
  useEffect(() => {
    SecureStore.getItemAsync(storageKey).then((value) => {
      if (value) setToken(value);
    });
    return () => active.current?.abort();
  }, []);
  async function login() {
    setBusy(true);
    setError("");
    try {
      const result = await new AssistantClient("", apiBase).request<{
        access_token: string;
      }>("/v1/sessions", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await SecureStore.setItemAsync(storageKey, result.access_token);
      setToken(result.access_token);
      setPassword("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!token) return;
    const client = new AssistantClient(token, apiBase);
    let live = true;
    (async () => {
      try {
        const projects = await client.request<{ items: { id: string }[] }>(
          "/v1/projects",
        );
        const bots = await client.request<{ items: { id: string }[] }>(
          `/v1/projects/${projects.items[0].id}/assistants`,
        );
        if (live) setAssistant(bots.items[0].id);
      } catch (e) {
        if (live) setError(String(e));
      }
    })();
    return () => {
      live = false;
    };
  }, [token]);
  async function send() {
    if (!input.trim() || busy || !assistant) return;
    setBusy(true);
    setError("");
    active.current = new AbortController();
    const text = input;
    setInput("");
    setMessages((m) => [...m, "You: " + text]);
    try {
      const result: ChatResult = await new AssistantClient(token, apiBase).chat(
        assistant,
        text,
        conversation,
        "extractive",
        active.current.signal,
      );
      setConversation(result.conversation_id);
      setMessages((m) => [
        ...m,
        "Assistant: " +
          result.text +
          result.citations
            .map((c) => `\nSource: ${c.title}, page ${c.page}`)
            .join(""),
      ]);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <SafeAreaView style={{ flex: 1, padding: 20 }}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        {!token ? (
          <View>
            <Text>Sign in to your assistant</Text>
            <TextInput
              accessibilityLabel="Email"
              autoCapitalize="none"
              value={email}
              onChangeText={setEmail}
            />
            <TextInput
              accessibilityLabel="Password"
              secureTextEntry
              value={password}
              onChangeText={setPassword}
            />
            <Button title="Sign in" onPress={login} disabled={busy} />
          </View>
        ) : (
          <>
            <ScrollView style={{ flex: 1 }}>
              {messages.map((text, i) => (
                <Text style={{ padding: 12 }} key={i}>
                  {text}
                </Text>
              ))}
            </ScrollView>
            <TextInput
              accessibilityLabel="Message"
              value={input}
              onChangeText={setInput}
              maxLength={4000}
            />
            <Button
              title={busy ? "Working…" : "Send"}
              disabled={busy || !assistant}
              onPress={send}
            />
            <Button title="Stop" onPress={() => active.current?.abort()} />
            <Button
              title="Sign out"
              onPress={async () => {
                await new AssistantClient(token, apiBase)
                  .request("/v1/sessions/current", { method: "DELETE" })
                  .catch(() => {});
                await SecureStore.deleteItemAsync(storageKey);
                setToken("");
                setMessages([]);
                setConversation(undefined);
              }}
            />
          </>
        )}
        {error && <Text accessibilityRole="alert">{error}</Text>}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
