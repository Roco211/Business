from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class RuntimeTurnContext:
    shop_id: str
    session_id: str
    source_message_id: str
    task_run_id: str
    input_kind: str
    source_text: Optional[str] = None
    media_ids: List[str] = field(default_factory=list)
    locale: str = "en-US"
    timezone: str = "UTC"
    shop_rules: Dict[str, object] = field(default_factory=dict)
    recent_messages: List[Dict[str, object]] = field(default_factory=list)
    pending_confirmation_id: Optional[str] = None


@dataclass(frozen=True)
class RuntimeRouteDecision:
    task_type: str
    assigned_employee_id: str
    transcript: Optional[str]
    payload: Dict[str, object] = field(default_factory=dict)


class RuntimeRouteBlocked(Exception):
    def __init__(self, error_code: str, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(error_message)
