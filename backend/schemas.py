"""
backend/schemas.py
──────────────────
Pydantic v2 schemas for the forensic ROI-inspection workflow.

Design rules enforced here (not just in prompts):
  • Every AI observation carries a 0.0-1.0 confidence score.
  • `details` is capped at 3 items so a VLM can never ramble.
  • Observations enter the system as "Unverified_Draft" and only an explicit
    human action moves them to "Verified" (human-in-the-loop gate).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal["PERSON", "VEHICLE", "TEXT_OR_CODE", "OBJECT", "ANOMALY"]
VerificationStatus = Literal["Unverified_Draft", "Verified"]
FindingRole = Literal["VICTIM", "SUSPECT", "WITNESS", "ITEM", "WEAPON", "TOOL", "STOLEN",
                      "VEHICLE", "PLATE", "ID", "LOCATION", "OTHER"]


# ── Scan request / VLM output ────────────────────────────────────────────────

class VLMScanRequest(BaseModel):
    """
    Operator-drawn region of interest on a paused video frame.

    Coordinates are RELATIVE (0.0-1.0 of frame width/height) so they are
    independent of how large the browser rendered the <video> element.
    Exactly one of `frame_offset` (0-based frame index) or `timestamp_ms`
    must be supplied.
    """

    model_config = ConfigDict(extra="forbid")

    video_id: str = Field(min_length=1, max_length=255)
    frame_offset: Optional[int] = Field(default=None, ge=0)
    timestamp_ms: Optional[int] = Field(default=None, ge=0)
    x1: float = Field(ge=0.0, le=1.0)
    y1: float = Field(ge=0.0, le=1.0)
    x2: float = Field(ge=0.0, le=1.0)
    y2: float = Field(ge=0.0, le=1.0)
    operator_id: str = Field(default="OPERATOR", min_length=1, max_length=100)

    @model_validator(mode="after")
    def _validate_position_and_box(self) -> "VLMScanRequest":
        if (self.frame_offset is None) == (self.timestamp_ms is None):
            raise ValueError("Provide exactly one of frame_offset or timestamp_ms")
        # Normalise a box dragged right-to-left / bottom-to-top.
        if self.x2 < self.x1:
            self.x1, self.x2 = self.x2, self.x1
        if self.y2 < self.y1:
            self.y1, self.y2 = self.y2, self.y1
        # Reject accidental clicks: ROI must cover a meaningful area.
        if (self.x2 - self.x1) < 0.005 or (self.y2 - self.y1) < 0.005:
            raise ValueError("Selected region is too small to analyse")
        return self


class VLMRawOutput(BaseModel):
    """Exact JSON shape the local VLM is constrained to emit (schema-guided)."""

    model_config = ConfigDict(extra="ignore")

    label: str = Field(min_length=1, max_length=120)
    category: Category
    readout_text: str = Field(max_length=500)
    details: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)

    @field_validator("details")
    @classmethod
    def _cap_details(cls, v: List[str]) -> List[str]:
        return [str(d)[:200] for d in v][:3]


class VLMAnalysisResult(BaseModel):
    """VLM observation AFTER objective-lexicon enforcement."""

    label: str
    category: Category
    readout_text: str
    details: List[str] = Field(max_length=3)
    # False means the raw model output contained subjective / conclusory terms
    # that had to be rewritten. The stored text is always the corrected text.
    objective_lexicon_compliant: bool
    confidence_score: float = Field(ge=0.0, le=1.0)


# ── Scan response / findings ─────────────────────────────────────────────────

class Finding(BaseModel):
    id: str
    evidence_id: str
    label: str
    category: Category
    readout_text: str
    details: List[str]
    objective_lexicon_compliant: bool
    confidence_score: float
    frame_index: int
    timestamp_ms: int
    timestamp_str: str
    roi_px: List[int]
    frame_sha256: str
    crop_sha256: str
    operator_id: str
    verification_status: VerificationStatus
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    role: Optional[FindingRole] = None          # what the investigator says this is
    subject_name: Optional[str] = None          # who/what it is, in the investigator's words
    source_reference: str
    created_at: Optional[str] = None


class ScanResponse(BaseModel):
    finding: Finding
    # 448x448 PNG patch actually sent to the VLM, so the investigator can see
    # exactly what the model saw.
    crop_preview_b64: str
    vlm_latency_ms: int


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operator_id: str = Field(min_length=1, max_length=100)
    role: Optional[FindingRole] = None
    subject_name: Optional[str] = Field(default=None, min_length=1, max_length=120)


class FindingEdit(BaseModel):
    """Operator correction. Any substantive edit resets verification."""

    model_config = ConfigDict(extra="forbid")

    operator_id: str = Field(min_length=1, max_length=100)
    label: Optional[str] = Field(default=None, min_length=1, max_length=120)
    readout_text: Optional[str] = Field(default=None, max_length=500)
    details: Optional[List[str]] = Field(default=None, max_length=3)
    role: Optional[FindingRole] = None
    subject_name: Optional[str] = Field(default=None, min_length=1, max_length=120)


class VideoMeta(BaseModel):
    evidence_id: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration_ms: int
    file_sha256: str


# ── Chain of custody ─────────────────────────────────────────────────────────

class AuditLogEntry(BaseModel):
    case_id: Optional[str] = None
    evidence_id: Optional[str] = None
    file_hash_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    operator_id: str = "SYSTEM"
    action: str
    timestamp: datetime
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    id: str
    case_id: str
    file_path: str
    file_hash: Optional[str] = None
    file_type: str
    verification_status: VerificationStatus = "Unverified_Draft"
    analysis_data: Optional[dict[str, Any]] = None
