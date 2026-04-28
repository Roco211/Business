from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

UTC = timezone.utc


@dataclass
class VerificationCodeRecord:
    phone: str
    code_hash: str
    expires_at: datetime
    consumed: bool = False


class VerificationCodeStore:
    def __init__(self) -> None:
        self._records: dict[str, VerificationCodeRecord] = {}

    def issue_code(self, *, phone: str, ttl_seconds: int) -> str:
        code = _generate_code()
        self._records[_normalize_phone(phone)] = VerificationCodeRecord(
            phone=_normalize_phone(phone),
            code_hash=_hash_code(code),
            expires_at=_now() + timedelta(seconds=ttl_seconds),
        )
        return code

    def consume_code(self, *, phone: str, code: str) -> bool:
        normalized_phone = _normalize_phone(phone)
        record = self._records.get(normalized_phone)
        if record is None or record.consumed:
            return False
        if record.expires_at < _now():
            return False
        if not secrets.compare_digest(record.code_hash, _hash_code(code)):
            return False
        record.consumed = True
        return True

    def reset(self) -> None:
        self._records.clear()


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _generate_code() -> str:
    while True:
        code = f"{secrets.randbelow(1_000_000):06d}"
        if code != "888888":
            return code


_default_store = VerificationCodeStore()


def get_default_verification_code_store() -> VerificationCodeStore:
    return _default_store
