// frontend/src/services/forensicApi.ts
// Typed client for the forensic workbench API (/api/v1).

const BASE = "/api/v1";

export type Category = "PERSON" | "VEHICLE" | "TEXT_OR_CODE" | "OBJECT" | "ANOMALY";
export type VerificationStatus = "Unverified_Draft" | "Verified";
export type FindingRole =
  | "VICTIM" | "SUSPECT" | "WITNESS" | "ITEM" | "WEAPON" | "TOOL" | "STOLEN"
  | "VEHICLE" | "PLATE" | "ID" | "LOCATION" | "OTHER";

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
  role?: FindingRole | null;
  subject_name?: string | null;
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

  verify: (id: string, operatorId: string, role?: FindingRole | null, subjectName?: string | null) =>
    request<Finding>(`/findings/${id}/verify`, {
      method: "POST",
      body: JSON.stringify({
        operator_id: operatorId,
        ...(role ? { role } : {}),
        ...(subjectName && subjectName.trim() ? { subject_name: subjectName.trim() } : {}),
      }),
    }),

  unverify: (id: string, operatorId: string) =>
    request<Finding>(`/findings/${id}/unverify`, {
      method: "POST",
      body: JSON.stringify({ operator_id: operatorId }),
    }),

  edit: (
    id: string,
    operatorId: string,
    changes: { label?: string; readout_text?: string; details?: string[]; role?: FindingRole; subject_name?: string }
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
  totals: {
    clues: number; matches: number; strong: number; medium: number; weak: number;
    keywords: number; evidence: number;
  };
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

export interface ReviewItem {
  id: string;
  evidence_id: string;
  file_name: string;
  label: string;
  class_name: string | null;
  confidence: number;
  timestamp_str: string | null;
  readout_text: string | null;
  verification_status: string;
}

export const investigationApi = {
  reviewQueue: (caseId: string) =>
    request<{ items: ReviewItem[]; counts: Record<string, number> }>(`/cases/${caseId}/review-queue`),
  reviewDetection: (id: string, decision: "confirm" | "reject" | "relabel", operatorId: string, className?: string) =>
    request<{ id: string; decision: string; label: string }>(`/detections/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, operator_id: operatorId, class_name: className }),
    }),
  cropUrl: (detectionId: string) => `${BASE}/detections/${detectionId}/crop`,
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

// ── Case clues, transcripts and global overview ──────────────────────────────

export interface CaseClue {
  id: string;
  evidence_id: string;
  file_name: string | null;
  kind: string;
  value: string;
  confidence: number;
  source: string;
  timestamp_ms: number | null;
  context: string | null;
  match_ids: string[];
}

export interface TranscriptTerm {
  kind: string;
  value: string;
  matches: { id: string; strength: MatchStrength; score: number; also_in: string[] }[];
}

export interface TranscriptChunk {
  id: string;
  text: string;
  page: number | null;
  source: "TRANSCRIPT" | "DOCUMENT";
  ocr: boolean;
  start_ms: number | null;
  end_ms: number | null;
  terms: TranscriptTerm[];
}

export interface CaseTranscripts {
  evidence: {
    evidence_id: string;
    file_name: string;
    file_type: string;
    analysis_status: string;
    transcription_status: string | null;
    chunks: TranscriptChunk[];
    matched_terms: number;
  }[];
  totals: { passages: number; matched_terms: number };
}

export interface OverviewLead {
  id: string;
  case_id: string;
  case_number: string;
  case_title: string;
  kind: string;
  value: string;
  strength: MatchStrength;
  score: number;
  match_type: string;
  explanation: string;
  verified: boolean;
  files: string[];
  sources: { file: string; at: string | null; source: string | null; reading: string }[];
}

export interface OverviewGap {
  id: string;
  severity: "high" | "medium" | "low";
  text: string;
  case_id: string;
  case_number: string;
  kind: string;
}

export interface OverviewActivity {
  id: string;
  seq: number;
  action: string;
  text: string;
  case_number: string | null;
  operator: string;
  time: string;
}

export interface Overview {
  leads: OverviewLead[];
  gaps: OverviewGap[];
  activity: OverviewActivity[];
  stats: { cases: number; evidence: number; clues: number; matches: number };
}

export const caseViewsApi = {
  caseClues: (caseId: string) => request<CaseClue[]>(`/cases/${caseId}/clues`),
  transcripts: (caseId: string) => request<CaseTranscripts>(`/cases/${caseId}/transcripts`),
  overview: () => request<Overview>("/overview"),
};

// ── Key findings + event timeline ────────────────────────────────────────────

export interface KFSupport {
  evidence_id: string;
  file_name: string;
  source: string | null;
  at: string | null;
  text: string;
  verified: boolean;
  clue_id: string | null;
}

export interface KFPhoto {
  url: string;
  caption: string;
  evidence_id: string;
  file_name: string;
  at: string | null;
  source: string | null;
  verified: boolean;
  role: string | null;
}

export interface KFPerson {
  id: string;
  name: string;
  aliases: string[];
  role: string | null;
  role_source: string | null;
  needs_review: boolean;
  verified: boolean;
  evidence_count: number;
  strength: MatchStrength | null;
  photos: KFPhoto[];
  support: KFSupport[];
}

export interface KFId {
  id: string;
  value: string;
  verified: boolean;
  evidence_count: number;
  strength: MatchStrength | null;
  support: KFSupport[];
  label: string | null;
}

export interface KFItem {
  id: string;
  name: string;
  display: string;
  item_class: string;
  role: string | null;
  role_source: string | null;
  verified: boolean;
  evidence_count: number;
  strength: MatchStrength | null;
  photos: KFPhoto[];
  support: KFSupport[];
}

export interface KFPlate {
  plate: string;
  strength: MatchStrength | null;
  match_type: string | null;
  verified: boolean;
  evidence_count: number;
  support: KFSupport[];
}

export interface KFVehicle {
  id: string;
  description: string;
  display: string;
  verified: boolean;
  evidence_count: number;
  strength: MatchStrength | null;
  plates: KFPlate[];
  plate_inferred: boolean;
  photos: KFPhoto[];
  support: KFSupport[];
}

export interface KeyFindingsData {
  people: KFPerson[];
  ids: KFId[];
  items: KFItem[];
  vehicles: KFVehicle[];
  unlinked_plates: KFPlate[];
  totals: Record<string, number>;
  notes: string[];
}

export interface TimelineEvent {
  id: string;
  evidence_id: string;
  file_name: string;
  file_type: string | null;
  kind: "message" | "mention" | "speech" | "scan" | "video" | "document";
  label: string;
  text: string;
  time: string | null;
  date_known: boolean;
  assumed_date: boolean;
  observed: boolean;
  offset_ms: number | null;
  terms: { kind: string; value: string; norm: string }[];
}

export interface EventTimelineData {
  events: TimelineEvent[];
  groups: {
    id: string;
    start: string;
    end: string;
    evidence_ids: string[];
    file_names: string[];
    event_ids: string[];
    linked_undated_ids: string[];
    shared_terms: { kind: string; value: string }[];
    assumed_date: boolean;
    summary: string;
  }[];
  assumed_date: string | null;
  stats: Record<string, number>;
  notes: string[];
}

export const caseBoardApi = {
  keyFindings: (caseId: string) => request<KeyFindingsData>(`/cases/${caseId}/key-findings`),
  eventTimeline: (caseId: string, windowMin = 45) =>
    request<EventTimelineData>(`/cases/${caseId}/event-timeline?window_min=${windowMin}`),
  setRecordingStart: (evidenceId: string, value: string) =>
    request<unknown>(`/evidence/${evidenceId}/recording-start`, {
      method: "PUT",
      body: JSON.stringify({ recording_start: value }),
    }),
};
