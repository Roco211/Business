import importlib.util
from pathlib import Path
import sys

from fastapi.testclient import TestClient


def load_create_app():
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))
    sys.modules.pop("app", None)
    main_path = backend_root / "app" / "main.py"
    spec = importlib.util.spec_from_file_location("foundation_backend_main", main_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend app module")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_app


def test_health_returns_ok_payload() -> None:
    client = TestClient(load_create_app()())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
