"""
backend/modules/vision/vlm_client.py
────────────────────────────────────
Async client for the LOCAL vision-language model served by Ollama
(default: Qwen2.5-VL-7B).

Guarantees:
  • Air-gapped — the endpoint host must be loopback; anything else is refused
    at construction time, so a bad .env can never leak an evidence crop.
  • Schema-constrained — Ollama's `format` parameter receives the JSON Schema
    of VLMRawOutput, so decoding is grammar-constrained to that shape.
  • Deterministic — temperature 0.0, bounded `num_predict`.
  • Objective — every output is passed through the objective-lexicon
    enforcer before it is returned.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from backend.config import settings
from backend.modules.vision.objective_lexicon import enforce_many, enforce_objective_lexicon
from backend.schemas import VLMAnalysisResult, VLMRawOutput

logger = logging.getLogger(__name__)

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

SYSTEM_PROMPT = (
    "You are an air-gapped forensic inspection engine. Analyze the provided "
    "image patch. Provide objective, purely descriptive observations only "
    "(e.g., 'red liquid', 'metallic object'). Never assume guilt, criminal "
    "intent, or legal classification. Output strict JSON only matching the "
    "schema."
)

USER_PROMPT = (
    "Extract text, identify physical attributes, and list objective details. "
    "Set readout_text to the exact visible characters, or \"NONE\" if no text "
    "is legible. Do not guess unreadable characters."
)


class VLMError(RuntimeError):
    """Base class for VLM failures."""


class VLMUnavailableError(VLMError):
    """The local model server could not be reached / timed out."""


class VLMOutputError(VLMError):
    """The model answered but not with schema-valid JSON."""


@dataclass(frozen=True)
class VLMCallResult:
    result: VLMAnalysisResult
    raw_response: str          # untouched model text — stored encrypted in the audit trail
    latency_ms: int
    model: str


def _assert_loopback(url: str) -> None:
    host = urlparse(url).hostname
    if host not in _LOOPBACK_HOSTS:
        raise ValueError(
            f"Refusing non-local VLM endpoint '{url}'. ForenSight is air-gapped: "
            "only 127.0.0.1 / localhost / ::1 are permitted."
        )


def _coerce_raw(data: Dict[str, Any]) -> Dict[str, Any]:
    """Tolerate common small-model slips without accepting wrong categories."""
    out = dict(data)
    if isinstance(out.get("category"), str):
        out["category"] = out["category"].strip().upper()
    if isinstance(out.get("details"), str):
        out["details"] = [out["details"]]
    if out.get("readout_text") is None:
        out["readout_text"] = "NONE"
    # Some models answer 0-100 instead of 0-1.
    try:
        conf = float(out.get("confidence_score"))
        if 1.0 < conf <= 100.0:
            conf = conf / 100.0
        out["confidence_score"] = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        pass
    return out


def parse_model_output(raw_text: str) -> VLMAnalysisResult:
    """Validate raw model text and apply objective-lexicon enforcement."""
    try:
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("top-level JSON is not an object")
        raw = VLMRawOutput.model_validate(_coerce_raw(data))
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        raise VLMOutputError(f"VLM output failed schema validation: {exc}") from exc

    label, label_ok = enforce_objective_lexicon(raw.label)
    readout, readout_ok = enforce_objective_lexicon(raw.readout_text)
    details, details_ok = enforce_many(raw.details)

    return VLMAnalysisResult(
        label=label,
        category=raw.category,
        readout_text=readout,
        details=details,
        objective_lexicon_compliant=label_ok and readout_ok and details_ok,
        confidence_score=raw.confidence_score,
    )


class VLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        self.endpoint = f"{(base_url or settings.OLLAMA_BASE_URL).rstrip('/')}/api/generate"
        _assert_loopback(self.endpoint)
        self.model = model or settings.OLLAMA_VISION_MODEL
        self.timeout_s = timeout_s or settings.VLM_TIMEOUT_S
        self.max_tokens = max_tokens or settings.VLM_MAX_TOKENS

    async def analyze_patch(self, patch_b64: str) -> VLMCallResult:
        """Send one Base64 PNG patch to the local VLM and return the validated result."""
        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": USER_PROMPT,
            "images": [patch_b64],
            "format": VLMRawOutput.model_json_schema(),   # schema-constrained decoding
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": self.max_tokens},
        }

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise VLMUnavailableError(
                f"Local VLM returned HTTP {exc.response.status_code} "
                f"(is '{self.model}' pulled? `ollama pull {self.model}`): {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise VLMUnavailableError(
                f"Local VLM unreachable at {self.endpoint}. Is Ollama running? ({exc})"
            ) from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        raw_text = response.json().get("response", "")
        result = parse_model_output(raw_text)
        return VLMCallResult(result=result, raw_response=raw_text, latency_ms=latency_ms, model=self.model)
