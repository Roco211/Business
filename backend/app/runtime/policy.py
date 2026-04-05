from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    outcome: str
    confirmation_type: str | None


def evaluate_runtime_policy(*, task_type: str) -> PolicyDecision:
    if task_type in {"voice-stock-in", "photo-stock-in"}:
        return PolicyDecision(
            outcome="require-confirmation",
            confirmation_type="low-confidence-recognition",
        )
    if task_type == "receipt-ocr":
        return PolicyDecision(
            outcome="require-confirmation",
            confirmation_type="receipt-stock-in-batch",
        )
    return PolicyDecision(outcome="allow", confirmation_type=None)
