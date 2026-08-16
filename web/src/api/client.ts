const BASE = "/api";
const TOKEN_KEY = "shortube_api_token";

export function getApiToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setApiToken(token: string): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getApiToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...authHeaders() },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    if (res.status === 401) {
      throw new Error("Unauthorized — check your API token in Settings");
    }
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export interface Trend {
  id: number;
  title: string;
  source: string;
  score: number;
  url: string | null;
}

export interface Job {
  id: number;
  video_id: number;
  job_type: string;
  status: string;
  progress: number;
  error: string | null;
  topic_title: string;
}

export interface Video {
  id: number;
  topic_title: string;
  status: string;
  video_path: string | null;
  youtube_url: string | null;
  created_at: string;
  thumbnail_path: string | null;
}

export interface Topic {
  id: number;
  title: string;
  niche: string;
  source: string;
  score: number;
  used: boolean;
}

export interface Settings {
  [key: string]: unknown;
}

export interface GenerateResponse {
  job_id: number;
  video_id: number;
  topic: string;
  status: string;
  progress: number;
}

export const api = {
  trends: (niche?: string, count = 10) => {
    const params = new URLSearchParams();
    if (niche) params.set("niche", niche);
    params.set("count", String(count));
    return request<{ trends: Trend[] }>(`/trends?${params}`);
  },

  topics: (limit = 100) =>
    request<{ topics: Topic[] }>(`/topics?limit=${limit}`),

  generate: (topic: string, privacy = "private", niche?: string) =>
    request<GenerateResponse>("/generate", {
      method: "POST",
      body: JSON.stringify({ topic, privacy, niche }),
    }),

  auto: (niche?: string, privacy = "private") =>
    request<GenerateResponse>("/auto", {
      method: "POST",
      body: JSON.stringify({ niche, privacy }),
    }),

  jobs: (limit = 50) =>
    request<{ jobs: Job[] }>(`/jobs?limit=${limit}`),

  job: (id: number) =>
    request<{ job: Job }>(`/jobs/${id}`),

  videos: (limit = 50) =>
    request<{ videos: Video[] }>(`/videos?limit=${limit}`),

  video: (id: number) =>
    request<{ video: Video }>(`/videos/${id}`),

  settings: () =>
    request<{ settings: Settings }>("/settings"),

  updateSettings: (settings: Record<string, unknown>) =>
    request<{ status: string }>("/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),

  templates: () =>
    request<{ templates: { id: string; name: string }[] }>("/templates"),

  schedule: () => request<{ schedule: Record<string, unknown> }>("/schedule"),

  updateSchedule: (schedule: Record<string, unknown>) =>
    request<{ schedule: Record<string, unknown> }>("/schedule", {
      method: "PUT",
      body: JSON.stringify(schedule),
    }),

  channels: () =>
    request<{ channels: { id: string; title: string }[] }>("/channels"),

  retry: (videoId: number) =>
    request<GenerateResponse>(`/retry/${videoId}`, {
      method: "POST",
    }),

  health: () => request<{ status: string }>("/health"),
};

/**
 * WebSocket with automatic reconnection (exponential backoff, capped).
 * After reconnect attempts are exhausted the caller gets `reconnect-failed`
 * so it can fall back to polling.
 */
export function connectJobWebSocket(
  jobId: number,
  onMessage: (data: Record<string, unknown>) => void,
  onError?: (err: Event) => void,
): { close: () => void } {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const token = getApiToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  const url = `${protocol}//${window.location.host}/api/ws/job/${jobId}${query}`;

  const MAX_RECONNECT_ATTEMPTS = 10;
  let socket: WebSocket | null = new WebSocket(url);
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closedByUser = false;

  const attach = (s: WebSocket) => {
    s.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch {
        // ignore malformed frames
      }
    };
    s.onerror = (ev) => onError?.(ev);
    s.onclose = () => {
      if (closedByUser) return;
      if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        onError?.(new Event("reconnect-failed"));
        return;
      }
      reconnectAttempts += 1;
      const delay = Math.min(1000 * 2 ** reconnectAttempts, 15000);
      reconnectTimer = setTimeout(() => {
        if (closedByUser) return;
        socket = new WebSocket(url);
        attach(socket);
      }, delay);
    };
  };
  attach(socket);

  return {
    close: () => {
      closedByUser = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    },
  };
}
