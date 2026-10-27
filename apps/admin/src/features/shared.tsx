import { useEffect, useState } from "react";
import { client } from "../model";
export function useResource<T>(url: string, version = 0) {
  const [data, setData] = useState<T>(),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setData(undefined);
    setError("");
    if (url)
      client
        .request<T>(url)
        .then((v) => {
          if (active) setData(v);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [url, version]);
  return { data, error };
}
export function useTask() {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function task(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, task };
}
export function ErrorNotice({ error }: { error?: string }) {
  return error ? (
    <p className="error" role="alert">
      {error}
    </p>
  ) : null;
}
export function downloadJson(name: string, data: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
