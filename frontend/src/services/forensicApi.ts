// frontend/src/services/forensicApi.ts
// Typed client for the forensic workbench API (/api/v1).

const BASE = "/api/v1";

export type Category = "PERSON" | "VEHICLE" | "TEXT_OR_CODE" | "OBJECT" | "ANOMALY";
export type VerificationStatus = "Unverified_Draft" | "Verified";

export interface Finding {
  id: string;
  evidence_id: string;
  label: string;
  category: Category;
  readout_text: string;
  details: string[];
  objective_lexicon_compliant: boolean;
  confidence_score: number; // 0.0 - 1.0
  frame_index: number;
  timestamp_ms: number;
  timestamp_str: string; // HH:MM:SS:MS
  roi_px: number[];
  frame_sha256: string;
  crop_sha256: string;
  operator_id: string;
  verification_status: VerificationStatus;
  verified_by: string | null;
  verified_at: string | null;
  source_reference: string;
  created_at?: string | null;
}

export interface ScanResponse {
  finding: Finding;
  crop_preview_b64: string;
  vlm_latency_ms: number;
}

export interface VideoMeta {
  evidence_id: string;
  fps: number;
  frame_count: number;
  width: number;
  height: number;
  duration_ms: number;
  file_sha256: string;
}

export interface RelativeBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface GraphNodeData {
  id: string;
  label: string;
  node_type: "Person" | "Vehicle" | "Item" | "Text" | "Evidence";
  readout?: string | null;
  confidence: number | null;
  finding_ids: string[];
  evidence_ids: string[];
  first_seen?: string | null;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  relation: string;
  label: string;
  reason: string;
  source_refs: string[];
}

export interface CaseGraph {
  nodes: { data: GraphNodeData }[];
  edges: { data: GraphEdgeData }[];
  meta: { finding_count: number; window_s: number; note: string };
}

export interface TimelineTrack {
  id: string;
  name: string;
  file_type: string;
}

export interface TimelineItem {
  id: string;
  track: string;
  kind: "finding" | "transcript";
  start_ms: number;
  end_ms: number | null;
  label: string;
  category: Category | null;
  confidence: number | null;
  verified: boolean;
  text: string | null;
  timestamp_str: string;
}

export interface CaseTimeline {
  tracks: TimelineTrack[];
  items: TimelineItem[];
}

export interface ChainReport {
  ok: boolean;
  entries_checked: number;
  head_seq: number;
  head_hash: string;
  broken_at_seq: number | null;
  reason: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const forensicApi = {
  videoMeta: (evidenceId: string) => request<VideoMeta>(`/video/${evidenceId}/meta`),

  scanRoi: (payload: RelativeBox & { video_id: string; frame_offset: number; operator_id: string }) =>
    request<ScanResponse>("/scan-roi", { method: "POST", body: JSON.stringify(payload) }),

  findings: (evidenceId: string) => request<Finding[]>(`/evidence/${evidenceId}/findings`),

  verify: (id: string, operatorId: string) =>
    request<Finding>(`/findings/${id}/verify`, {
      method: "POST",
      body: JSON.stringify({ operator_id: operatorId }),
    }),

  unverify: (id: string, operatorId: string) =>
    request<Finding>(`/findings/${id}/unverify`, {
      method: "POST",
      body: JSON.stringify({ operator_id: operatorId }),
    }),

  edit: (
    id: string,
    operatorId: string,
    changes: { label?: string; readout_text?: string; details?: string[] }
  ) =>
    request<Finding>(`/findings/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ operator_id: operatorId, ...changes }),
    }),

  graph: (caseId: string) => request<CaseGraph>(`/cases/${caseId}/graph`),

  timeline: (caseId: string, includeDrafts = false) =>
    request<CaseTimeline>(`/cases/${caseId}/timeline?include_drafts=${includeDrafts}`),

  verifyChain: () => request<ChainReport>("/audit/verify"),
};

// ── Investigation (automatic analysis, correlation, map, report) ─────────────

export type MatchStrength = "STRONG" | "MEDIUM" | "WEAK";

export interface MatchMember {
  clue_id: string;
  evidence_id: string;
  file_name: string;
  file_type: string | null;
  value: string;
  source: string | null;
  timestamp_ms: number | null;
  timestamp_str: string | null;
  confidence: number;
  context: string | null;
  bbox: number[] | null;
  verified: boolean;
}

export interface ClueMatch {
  id: string;
  kind: string;
  match_type: "EXACT" | "OCR_VARIANT" | "FUZZY" | "APPEARANCE";
  value: string;
  score: number;
  strength: MatchStrength;
  evidence_ids: string[];
  occurrences: number;
  explanation: string;
  verified: boolean;
  needs_review: boolean;
  members: MatchMember[];
}

export interface Correlations {
  matches: ClueMatch[];
  totals: { clues: number; matches: number; strong: number; medium: number; weak: number; evidence: number };
}

export interface AnalysisStatus {
  running: boolean;
  items: {
    evidence_id: string;
    file_name: string;
    file_type: string;
    status: "NOT_RUN" | "RUNNING" | "COMPLETED" | "PARTIAL" | "FAILED";
    progress: number;
    message: string | null;
  }[];
}

export interface MapPoint {
  evidence_id: string;
  file_name: string;
  file_type: string;
  latitude: number | null;
  longitude: number | null;
  label: string | null;
  captured_at: string | null;
  match_ids: string[];
}

export interface CaseMapData {
  points: MapPoint[];
  unlocated: MapPoint[];
  links: { from: string; to: string; match_id: string; value: string; kind: string; strength: MatchStrength }[];
}

export interface EvidenceClue {
  id: string;
  evidence_id: string;
  kind: string;
  value: string;
  confidence: number;
  source: string;
  timestamp_ms: number | null;
  bbox: number[] | string | null; // [x1,y1,x2,y2] relative 0-1 (list, or a JSON string)
  context: string | null;
  matches: {
    match_id: string;
    strength: MatchStrength;
    match_type: string;
    score: number;
    explanation: string;
    also_in: MatchMember[];
  }[];
}

export const investigationApi = {
  analyzeCase: (caseId: string) =>
    request<{ status: string; evidence_count: number }>(`/cases/${caseId}/analyze`, { method: "POST" }),
  analyzeEvidence: (id: string) => request<{ status: string }>(`/evidence/${id}/analyze`, { method: "POST" }),
  status: (caseId: string) => request<AnalysisStatus>(`/cases/${caseId}/analysis-status`),
  correlations: (caseId: string) => request<Correlations>(`/cases/${caseId}/correlations`),
  clueGraph: (caseId: string, includeWeak = false) =>
    request<CaseGraph>(`/cases/${caseId}/clue-graph?include_weak=${includeWeak}`),
  map: (caseId: string) => request<CaseMapData>(`/cases/${caseId}/map`),
  setLocation: (evidenceId: string, latitude: number, longitude: number, label?: string) =>
    request<unknown>(`/evidence/${evidenceId}/location`, {
      method: "PUT",
      body: JSON.stringify({ latitude, longitude, label }),
    }),
  evidenceClues: (evidenceId: string) =>
    request<{ clues: EvidenceClue[]; matched_count: number }>(`/evidence/${evidenceId}/clues`),
  capabilities: () =>
    request<{ detector: boolean; ocr: boolean; detector_model: string; errors: Record<string, string> }>(
      "/capabilities"
    ),
  reportUrl: (caseId: string, download = false) => `${BASE}/cases/${caseId}/report?download=${download}`,
};
