from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class ReadinessCheck:
    key: str
    status: str
    summary: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
        }


def build_mock_guardrails_check(settings: Settings | None = None) -> ReadinessCheck:
    active_settings = settings or get_settings()
    violations = active_settings.production_mock_violations()
    if violations:
        return ReadinessCheck(
            key="mock_guardrails",
            status="degraded",
            summary="production mock configuration detected",
            details={
                "violation_count": len(violations),
                "violations": violations,
            },
        )
    return ReadinessCheck(
        key="mock_guardrails",
        status="ready",
        summary="production mock guardrails passed",
        details={
            "violation_count": 0,
            "violations": [],
        },
    )
