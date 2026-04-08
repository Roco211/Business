import json
from pathlib import Path

from app.main import create_app


REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "project_docs" / "generated" / "openapi-v1.json"


def _load_snapshot() -> dict[str, object]:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _current_openapi_schema() -> dict[str, object]:
    app = create_app()
    return app.openapi()


def test_openapi_contract_snapshot_matches_live_app_schema() -> None:
    assert SNAPSHOT_PATH.exists(), "Committed OpenAPI snapshot is missing"
    assert _load_snapshot() == _current_openapi_schema()
