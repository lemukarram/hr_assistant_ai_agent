import { useAuthStore } from "../store/auth";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const { accessToken, refreshToken, updateAccessToken, logout } = useAuthStore.getState();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  let response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  // Auto-refresh on 401
  if (response.status === 401 && refreshToken) {
    const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (refreshRes.ok) {
      const data = await refreshRes.json();
      updateAccessToken(data.access_token);
      headers["Authorization"] = `Bearer ${data.access_token}`;
      response = await fetch(`${BASE_URL}${path}`, { ...options, headers });
    } else {
      logout();
    }
  }

  return response;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "خطأ في الاتصال بالخادم" }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error("Request failed");
  return res.json();
}

export function createSSEStream(
  path: string,
  body: unknown,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void
): AbortController {
  const controller = new AbortController();
  const { accessToken } = useAuthStore.getState();

  fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  }).then(async (res) => {
    if (!res.ok || !res.body) {
      onError(new Error("Stream connection failed"));
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) { onDone(); break; }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data === "[DONE]") { onDone(); return; }
          if (data) {
            try {
              const parsed = JSON.parse(data);
              if (parsed.token) onChunk(parsed.token);
              if (parsed.type === "done") onDone();
            } catch { onChunk(data); }
          }
        }
      }
    }
  }).catch((err) => {
    if (err.name !== "AbortError") onError(err);
  });

  return controller;
}
