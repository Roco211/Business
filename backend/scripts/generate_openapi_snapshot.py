import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
OUTPUT_PATH = REPO_ROOT / "project_docs" / "generated" / "openapi-v2.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import create_app


def generate_openapi_snapshot() -> dict[str, object]:
    app = create_app()
    return app.openapi()


def write_openapi_snapshot(output_path: Path = OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = generate_openapi_snapshot()
    output_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    output_path = write_openapi_snapshot()
    print(output_path)


if __name__ == "__main__":
    main()
