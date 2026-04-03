from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.workers.celery_app import celery_app


def test_celery_app_uses_expected_name() -> None:
    assert celery_app.main == "ai_store_manager"
