from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class RuntimeTurnContext:
    input_type: str
    source_text: str = ""
    text_hint: str = ""
    media_ids: Sequence[str] = field(default_factory=list)


@dataclass
class RuntimeRouteDecision:
    task_type: str
    assigned_employee_id: str
    text: str


class RuntimeRouteBlocked(Exception):
    def __init__(self, error_code: str):
        self.error_code = error_code
        super().__init__(error_code)
