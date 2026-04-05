import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import get_session_factory
from app.services.demo_state import bootstrap_demo_state


def main() -> None:
    session = get_session_factory()()
    try:
        summary = bootstrap_demo_state(session)
    finally:
        session.close()
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
