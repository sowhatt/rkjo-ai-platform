"""Optional OpenAI-compatible HTTP chat provider for student study artifacts.

No requests are made until generate() is explicitly called. Configure a trusted
HTTPS endpoint and API key. Never log requests: excerpts may be copyrighted
coursework. Approval, privacy controls and policy checks remain outside this adapter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import httpx

from rkjo_education.curriculum.health_artifact_pipeline import (
    StudyGenerationError, StudyGenerationRequest,
)


@dataclass(frozen=True, slots=True)
class StudyHTTPConfig:
    endpoint: str
    api_key: str
    model: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Trusted HTTPS endpoint required")
        if not self.api_key.strip() or not self.model.strip():
            raise ValueError("API key and model must be provided")
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("Timeout must be between 1 and 120 seconds")


class HTTPStudyProvider:
    def __init__(
        self, config: StudyHTTPConfig,
        *,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
    ) -> None:
        self.config = config
        self.client_factory = client_factory

    def generate(self, request: StudyGenerationRequest) -> dict[str, object]:
        segments = [
            {"segment_id": segment_id, "text": text[:6000]}
            for segment_id, text in request.source_segments[:30]
        ]
        prompt = json.dumps({
            "ue_id": request.ue_id,
            "artifact_type": request.artifact_type.value,
            "source_segments": segments,
        }, ensure_ascii=False)
        body = {
            "model": self.config.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": request.instruction},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            with self.client_factory(timeout=self.config.timeout_seconds) as client:
                response = client.post(
                    self.config.endpoint,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                    json=body,
                )
                response.raise_for_status()
                response_data = response.json()
            text = response_data["choices"][0]["message"]["content"]
            if not isinstance(text, str):
                raise StudyGenerationError("Model response content is not text")
            result = json.loads(text)
        except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as exc:
            raise StudyGenerationError("Model provider request or JSON response failed") from exc
        if not isinstance(result, dict):
            raise StudyGenerationError("Structured model response must be an object")
        return result
