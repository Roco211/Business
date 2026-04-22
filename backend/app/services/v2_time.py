from datetime import datetime, timezone
UTC = timezone.utc


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
