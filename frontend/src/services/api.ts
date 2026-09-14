// frontend/src/services/api.ts
// Typed fetch wrapper for all /api/* endpoints

const BASE = "/api";

// ── Timeline Event (shared type) ────────────────────────────────────────────
export interface TimelineEvent {
  id: string;
  label: string;
  type: "login" | "transaction" | "detection" | "document" | "alert";
  time: string;
  timestamp: number; // 0–100 relative position
  entity?: string;
  entityType?: "person" | "device" | "account" | "network";
  risk?: "high" | "medium" | "low" | null;
  description?: string;
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Cases ───────────────────────────────────────────────────────────────────

export interface Case {
  id: string;
  case_number: string;
  title: string;
  description?: string;
  status: "OPEN" | "UNDER_REVIEW" | "CLOSED" | "ARCHIVED";
  created_by_name: string;
  created_at: string;
  updated_at: string;
  evidence_count?: number;
  evidence?: Evidence[];
}

export interface CreateCasePayload {
  title: string;
  description?: string;
  case_number?: string;
  created_by_name?: string;
}

export const casesApi = {
  list: () => request<Case[]>("/cases"),
  get: (id: string) => request<Case>(`/cases/${id}`),
  create: (payload: CreateCasePayload) =>
    request<Case>("/cases", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: string, payload: Partial<Case>) =>
    request<Case>(`/cases/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  delete: (id: string) => request<void>(`/cases/${id}`, { method: "DELETE" }),
  getTimeline: (id: string) => request<TimelineEvent[]>(`/cases/${id}/timeline`),
};

// ── Evidence ─────────────────────────────────────────────────────────────────

export interface Evidence {
  id: string;
  case_id: string;
  file_name: string;
  file_type: "IMAGE" | "VIDEO" | "AUDIO" | "DOCUMENT" | "OTHER";
  file_path: string;
  file_size: number;
  mime_type: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  uploaded_at: string;
  processed_at?: string;
  detections?: Detection[];
  case_title?: string;
  case_number?: string;
}

export interface Detection {
  id: string;
  evidence_id: string;
  label: string;
  confidence: number;
  bounding_box: string;
  frame_timestamp?: number;
  grad_cam_path?: string;
  created_at: string;
}

export const evidenceApi = {
  listAll: () => request<Evidence[]>("/evidence"),
  get: (id: string) => request<Evidence>(`/evidence/${id}`),
  upload: (formData: FormData) =>
    fetch(`${BASE}/evidence/upload`, { method: "POST", body: formData }).then(
      async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail || "Upload failed");
        }
        return res.json() as Promise<Evidence>;
      }
    ),
  delete: (id: string) => request<void>(`/evidence/${id}`, { method: "DELETE" }),
};
