from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from uuid import uuid4

from alembic import command
from alembic.config import Config
import httpx
import uvicorn


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.local_demo_smoke import LocalDemoSmokeError, run_local_demo_smoke  # noqa: E402
from scripts.run_system_check import main as run_system_check_main  # noqa: E402
from scripts.set_pilot_cutover import main as set_pilot_cutover_main  # noqa: E402


PROFILE_LOCAL_DEMO = "local-demo"
PROFILE_TRIAL = "trial"
MODE_SHADOW = "shadow"
MODE_OPEN = "open"
DEFAULT_RUNTIME_BASE_DIR = Path(tempfile.gettempdir()) / "ai-native-saas-cli"
DEFAULT_ARTIFACT_SEARCH_DIR = BACKEND_ROOT / "devdata" / "trial_calibration_artifacts"
DEFAULT_OWNER_EMAIL = "owner@example.com"
DEFAULT_OWNER_PASSWORD = "dev-password"
DEFAULT_SESSION_ID = "sess_default"
DEFAULT_MESSAGE_WAIT_SECONDS = 2.0
PENDING_TASK_RUN_STATUSES = {"created", "processing"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the top-level CLI for local experience and system checks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    up_parser = subparsers.add_parser("up", help="Prepare local runtime state and start the API service.")
    up_parser.add_argument("--profile", choices=[PROFILE_LOCAL_DEMO, PROFILE_TRIAL], default=PROFILE_LOCAL_DEMO)
    up_parser.add_argument("--host", default="127.0.0.1")
    up_parser.add_argument("--port", type=int, default=8001)
    up_parser.add_argument("--runtime-root", default=None)
    up_parser.add_argument("--artifact-path", default=None)

    check_parser = subparsers.add_parser("check", help="Run the unified system check through the top-level CLI.")
    check_parser.add_argument("--mode", choices=["local-demo", "trial", "pilot"], required=True)
    check_parser.add_argument("--api-base-url", default="http://127.0.0.1:8001")
    check_parser.add_argument("--auth-token", default=None)
    check_parser.add_argument("--login-email", default=None)
    check_parser.add_argument("--login-password", default=None)
    check_parser.add_argument("--hours", type=int, default=24)
    check_parser.add_argument("--max-fallback-rate", type=float, default=0.05)
    check_parser.add_argument("--max-low-confidence-rate", type=float, default=0.20)
    check_parser.add_argument("--output-dir", default=None)
    check_parser.add_argument("--runtime-root", default=None)

    demo_parser = subparsers.add_parser("demo", help="Bootstrap and print the current local demo snapshot.")
    demo_parser.add_argument("--api-base-url", default="http://127.0.0.1:8001")
    demo_parser.add_argument("--auth-token", default=None)
    demo_parser.add_argument("--login-email", default=os.getenv("SEED_OWNER_EMAIL", DEFAULT_OWNER_EMAIL))
    demo_parser.add_argument("--login-password", default=os.getenv("SEED_OWNER_PASSWORD", DEFAULT_OWNER_PASSWORD))

    ask_parser = subparsers.add_parser("ask", help="Send a text message to the default session and print the task snapshot.")
    ask_parser.add_argument("--api-base-url", default="http://127.0.0.1:8001")
    ask_parser.add_argument("--auth-token", default=None)
    ask_parser.add_argument("--login-email", default=os.getenv("SEED_OWNER_EMAIL", DEFAULT_OWNER_EMAIL))
    ask_parser.add_argument("--login-password", default=os.getenv("SEED_OWNER_PASSWORD", DEFAULT_OWNER_PASSWORD))
    ask_parser.add_argument("--session-id", default=None)
    ask_parser.add_argument("--text", required=True)
    ask_parser.add_argument("--client-request-id", default=None)
    ask_parser.add_argument("--wait-seconds", type=float, default=DEFAULT_MESSAGE_WAIT_SECONDS)

    cutover_parser = subparsers.add_parser("cutover", help="Apply pilot cutover mutations through the top-level CLI.")
    cutover_parser.add_argument("--mode", choices=["closed", MODE_SHADOW, MODE_OPEN], required=True)
    cutover_parser.add_argument("--api-base-url", default="http://127.0.0.1:8001")
    cutover_parser.add_argument("--auth-token", default=None)
    cutover_parser.add_argument("--login-email", default=None)
    cutover_parser.add_argument("--login-password", default=None)
    cutover_parser.add_argument("--runtime-root", default=None)
    cutover_parser.add_argument("--artifact-path", default=None)
    cutover_parser.add_argument("--note", default=None)
    cutover_parser.add_argument("--skip-preflight", action="store_true")
    return parser


def _resolve_runtime_root(*, profile: str, runtime_root: str | None, mode: str | None = None) -> Path:
    if runtime_root is not None:
        return Path(runtime_root).expanduser().resolve()
    suffix = profile
    if mode == "pilot":
        suffix = PROFILE_TRIAL
    return (DEFAULT_RUNTIME_BASE_DIR / suffix).resolve()


def _request_json(
    method: str,
    url: str,
    *,
    auth_token: str | None = None,
    payload: dict[str, object] | None = None,
) -> tuple[int, object]:
    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
    try:
        response = httpx.request(
            method,
            url,
            headers=headers,
            json=payload,
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Request failed for {method} {url}: {exc}") from exc

    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Response from {method} {url} was not valid JSON") from exc
    return response.status_code, body


def _expect_object(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} was not an object")
    return value


def _expect_data_object(*, status_code: int, body: object, label: str) -> dict[str, object]:
    if status_code >= 400:
        raise RuntimeError(f"{label} returned HTTP {status_code}: {body}")
    payload = _expect_object(body, label=label)
    data = payload.get("data")
    return _expect_object(data, label=f"{label} data")


def _expect_data_list(*, status_code: int, body: object, label: str) -> list[object]:
    if status_code >= 400:
        raise RuntimeError(f"{label} returned HTTP {status_code}: {body}")
    payload = _expect_object(body, label=label)
    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError(f"{label} data was not a list")
    return data


def _expect_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{label} was not a non-empty string")
    return value


def _resolve_auth_token(
    *,
    api_base_url: str,
    auth_token: str | None,
    login_email: str,
    login_password: str,
) -> str:
    if auth_token:
        return auth_token
    status_code, body = _request_json(
        "POST",
        f"{api_base_url.rstrip('/')}/api/v1/auth/login",
        payload={"email": login_email, "password": login_password},
    )
    login_data = _expect_data_object(status_code=status_code, body=body, label="POST /api/v1/auth/login")
    return _expect_string(login_data.get("access_token"), label="POST /api/v1/auth/login access_token")


def _resolve_session_id(*, api_base_url: str, auth_token: str, session_id: str | None) -> str:
    if session_id:
        return session_id
    status_code, body = _request_json(
        "POST",
        f"{api_base_url.rstrip('/')}/api/v1/sessions/bootstrap",
        auth_token=auth_token,
        payload={},
    )
    session_data = _expect_data_object(status_code=status_code, body=body, label="POST /api/v1/sessions/bootstrap")
    return _expect_string(session_data.get("session_id"), label="POST /api/v1/sessions/bootstrap session_id")


def _fetch_task_run(*, api_base_url: str, auth_token: str, task_run_id: str) -> dict[str, object]:
    status_code, body = _request_json(
        "GET",
        f"{api_base_url.rstrip('/')}/api/v1/task-runs/{task_run_id}",
        auth_token=auth_token,
    )
    return _expect_data_object(status_code=status_code, body=body, label=f"GET /api/v1/task-runs/{task_run_id}")


def _wait_for_task_run(
    *,
    api_base_url: str,
    auth_token: str,
    task_run_id: str,
    wait_seconds: float,
) -> dict[str, object]:
    deadline = time.monotonic() + max(wait_seconds, 0.0)
    while True:
        task_run = _fetch_task_run(api_base_url=api_base_url, auth_token=auth_token, task_run_id=task_run_id)
        task_status = str(task_run.get("status") or "")
        if task_status not in PENDING_TASK_RUN_STATUSES or time.monotonic() >= deadline:
            return task_run
        time.sleep(0.2)


def _normalize_recent_messages(messages: list[object]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for index, raw_message in enumerate(messages):
        message = _expect_object(raw_message, label=f"Recent message[{index}]")
        normalized.append(
            {
                "actor_type": message.get("actor_type"),
                "message_type": message.get("message_type"),
                "text": message.get("text"),
            }
        )
    return normalized


def _resolve_database_url(runtime_root: Path) -> str:
    return f"sqlite:///{runtime_root.joinpath('runtime.db').as_posix()}"


def _latest_json_file(search_dir: Path) -> Path:
    candidates = [path for path in search_dir.glob("*.json") if path.is_file()]
    if not candidates:
        raise RuntimeError(f"No JSON artifacts were found under '{search_dir}'")
    return max(candidates, key=lambda candidate: candidate.stat().st_mtime)


def _resolve_artifact_source(artifact_path: str | None) -> Path:
    if artifact_path is not None and artifact_path.strip():
        return Path(artifact_path).expanduser().resolve()
    return _latest_json_file(DEFAULT_ARTIFACT_SEARCH_DIR)


def _load_artifact_profile(artifact_path: Path) -> str:
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Artifact '{artifact_path}' did not contain a JSON object")
    trial_provider_profile = payload.get("trial_provider_profile")
    if not isinstance(trial_provider_profile, str) or not trial_provider_profile.strip():
        raise RuntimeError(f"Artifact '{artifact_path}' did not include a non-empty trial_provider_profile")
    return trial_provider_profile.strip()


def _prepare_runtime_root(runtime_root: Path) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "artifacts").mkdir(parents=True, exist_ok=True)
    (runtime_root / "dataset").mkdir(parents=True, exist_ok=True)
    (runtime_root / "shift-bundles").mkdir(parents=True, exist_ok=True)


def _apply_runtime_env(profile: str, runtime_root: Path, artifact_path: Path | None, host: str, port: int) -> None:
    os.environ["DATABASE_URL"] = _resolve_database_url(runtime_root)
    os.environ["APP_HOST"] = host
    os.environ["APP_PORT"] = str(port)
    os.environ["SEED_OWNER_EMAIL"] = DEFAULT_OWNER_EMAIL
    os.environ["SEED_OWNER_PASSWORD"] = DEFAULT_OWNER_PASSWORD

    trial_only_keys = [
        "TRIAL_PROVIDER_PROFILE",
        "ASR_PROVIDER_LABEL",
        "OCR_PROVIDER_LABEL",
        "VISION_PROVIDER_LABEL",
        "TRIAL_CALIBRATION_DATASET_DIR",
        "TRIAL_CALIBRATION_ARTIFACTS_DIR",
        "LIVE_PILOT_ALLOWED_SHOP_IDS",
        "OBJECT_STORAGE_BUCKET",
        "OBJECT_STORAGE_REGION",
        "OBJECT_STORAGE_ENDPOINT_URL",
        "OBJECT_STORAGE_ACCESS_KEY",
        "OBJECT_STORAGE_SECRET_KEY",
        "ASR_PROVIDER_API_URL",
        "ASR_PROVIDER_API_KEY",
        "ASR_PROVIDER_MODEL",
        "OCR_PROVIDER_API_URL",
        "OCR_PROVIDER_API_KEY",
        "OCR_PROVIDER_MODEL",
        "VISION_PROVIDER_API_URL",
        "VISION_PROVIDER_API_KEY",
        "VISION_PROVIDER_MODEL",
    ]
    if profile == PROFILE_LOCAL_DEMO:
        os.environ["APP_RUNTIME_MODE"] = PROFILE_LOCAL_DEMO
        os.environ["OBJECT_STORAGE_PROVIDER"] = "mock"
        os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"
        os.environ["ASR_PROVIDER"] = "mock"
        os.environ["OCR_PROVIDER"] = "mock"
        os.environ["VISION_PROVIDER"] = "mock"
        os.environ["ASR_ALLOW_MOCK_FALLBACK"] = "1"
        os.environ["OCR_ALLOW_MOCK_FALLBACK"] = "1"
        os.environ["VISION_ALLOW_MOCK_FALLBACK"] = "1"
        for key in trial_only_keys:
            os.environ.pop(key, None)
        return

    if artifact_path is None:
        raise RuntimeError("Trial profile requires an artifact path")

    copied_artifact = runtime_root / "artifacts" / artifact_path.name
    shutil.copy2(artifact_path, copied_artifact)
    os.environ["APP_RUNTIME_MODE"] = PROFILE_TRIAL
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "0"
    os.environ["TRIAL_PROVIDER_PROFILE"] = _load_artifact_profile(copied_artifact)
    os.environ["ASR_PROVIDER_LABEL"] = "asr-primary"
    os.environ["OCR_PROVIDER_LABEL"] = "ocr-primary"
    os.environ["VISION_PROVIDER_LABEL"] = "vision-primary"
    os.environ["TRIAL_CALIBRATION_DATASET_DIR"] = str(runtime_root / "dataset")
    os.environ["TRIAL_CALIBRATION_ARTIFACTS_DIR"] = str(runtime_root / "artifacts")
    os.environ["LIVE_PILOT_ALLOWED_SHOP_IDS"] = "shop_default"
    os.environ["OBJECT_STORAGE_PROVIDER"] = "s3-compatible"
    os.environ["OBJECT_STORAGE_BUCKET"] = "trial-bucket"
    os.environ["OBJECT_STORAGE_REGION"] = "ap-southeast-1"
    os.environ["OBJECT_STORAGE_ENDPOINT_URL"] = "https://s3.example.com"
    os.environ["OBJECT_STORAGE_ACCESS_KEY"] = "access"
    os.environ["OBJECT_STORAGE_SECRET_KEY"] = "secret"
    os.environ["ASR_PROVIDER"] = "real-provider"
    os.environ["ASR_PROVIDER_API_URL"] = "https://asr.example.com/v1"
    os.environ["ASR_PROVIDER_API_KEY"] = "asr-key"
    os.environ["ASR_PROVIDER_MODEL"] = "asr-model"
    os.environ["ASR_ALLOW_MOCK_FALLBACK"] = "0"
    os.environ["OCR_PROVIDER"] = "real-provider"
    os.environ["OCR_PROVIDER_API_URL"] = "https://ocr.example.com/v1"
    os.environ["OCR_PROVIDER_API_KEY"] = "ocr-key"
    os.environ["OCR_PROVIDER_MODEL"] = "ocr-model"
    os.environ["OCR_ALLOW_MOCK_FALLBACK"] = "0"
    os.environ["VISION_PROVIDER"] = "real-provider"
    os.environ["VISION_PROVIDER_API_URL"] = "https://vision.example.com/v1"
    os.environ["VISION_PROVIDER_API_KEY"] = "vision-key"
    os.environ["VISION_PROVIDER_MODEL"] = "vision-model"
    os.environ["VISION_ALLOW_MOCK_FALLBACK"] = "0"


def run_alembic_upgrade(database_url: str) -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def run_uvicorn_app(*, host: str, port: int) -> int:
    uvicorn.run("app.main:create_app", factory=True, host=host, port=port)
    return 0


def _handle_up(args: argparse.Namespace) -> int:
    runtime_root = _resolve_runtime_root(profile=args.profile, runtime_root=args.runtime_root)
    _prepare_runtime_root(runtime_root)
    artifact_path = None
    if args.profile == PROFILE_TRIAL:
        artifact_path = _resolve_artifact_source(args.artifact_path)
    _apply_runtime_env(args.profile, runtime_root, artifact_path, args.host, args.port)
    run_alembic_upgrade(os.environ["DATABASE_URL"])
    return run_uvicorn_app(host=args.host, port=args.port)


def _handle_check(args: argparse.Namespace) -> int:
    argv: list[str] = [
        "--mode",
        args.mode,
        "--api-base-url",
        args.api_base_url,
    ]
    if args.auth_token:
        argv.extend(["--auth-token", args.auth_token])
    if args.login_email:
        argv.extend(["--login-email", args.login_email])
    if args.login_password:
        argv.extend(["--login-password", args.login_password])
    if args.hours != 24:
        argv.extend(["--hours", str(args.hours)])
    if args.max_fallback_rate != 0.05:
        argv.extend(["--max-fallback-rate", str(args.max_fallback_rate)])
    if args.max_low_confidence_rate != 0.20:
        argv.extend(["--max-low-confidence-rate", str(args.max_low_confidence_rate)])
    output_dir = args.output_dir
    if output_dir is None and args.mode == "pilot":
        runtime_root = _resolve_runtime_root(profile=PROFILE_TRIAL, runtime_root=args.runtime_root, mode=args.mode)
        output_dir = str(runtime_root / "shift-bundles")
    if output_dir:
        argv.extend(["--output-dir", output_dir])
    return run_system_check_main(argv)


def _handle_demo(args: argparse.Namespace) -> int:
    try:
        result = run_local_demo_smoke(
            api_base_url=args.api_base_url,
            auth_token=args.auth_token,
            login_email=args.login_email,
            login_password=args.login_password,
        )
    except LocalDemoSmokeError as exc:
        raise RuntimeError(f"Local demo smoke failed: {exc}") from exc

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


def _handle_ask(args: argparse.Namespace) -> int:
    api_base_url = args.api_base_url.rstrip("/")
    auth_token = _resolve_auth_token(
        api_base_url=api_base_url,
        auth_token=args.auth_token,
        login_email=args.login_email,
        login_password=args.login_password,
    )
    session_id = _resolve_session_id(api_base_url=api_base_url, auth_token=auth_token, session_id=args.session_id)
    client_request_id = args.client_request_id or f"cli-ask-{uuid4().hex[:12]}"
    status_code, body = _request_json(
        "POST",
        f"{api_base_url}/api/v1/sessions/{session_id}/messages",
        auth_token=auth_token,
        payload={
            "message_type": "text",
            "text": args.text,
            "media_ids": [],
            "client_request_id": client_request_id,
        },
    )
    message_data = _expect_data_object(
        status_code=status_code,
        body=body,
        label=f"POST /api/v1/sessions/{session_id}/messages",
    )
    task_run_id = _expect_string(message_data.get("task_run_id"), label="POST /api/v1/sessions task_run_id")
    task_run = _wait_for_task_run(
        api_base_url=api_base_url,
        auth_token=auth_token,
        task_run_id=task_run_id,
        wait_seconds=args.wait_seconds,
    )
    messages_status_code, messages_body = _request_json(
        "GET",
        f"{api_base_url}/api/v1/sessions/{session_id}/messages?limit=4",
        auth_token=auth_token,
    )
    recent_messages = _normalize_recent_messages(
        _expect_data_list(
            status_code=messages_status_code,
            body=messages_body,
            label=f"GET /api/v1/sessions/{session_id}/messages",
        )
    )
    print(
        json.dumps(
            {
                "api_base_url": api_base_url,
                "session_id": session_id,
                "message": message_data,
                "task_run": task_run,
                "recent_messages": recent_messages,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if task_run.get("error_code") else 0


def _resolve_cutover_artifact_path(mode: str, runtime_root: Path, artifact_path: str | None) -> str | None:
    if mode not in {MODE_SHADOW, MODE_OPEN}:
        return artifact_path
    if artifact_path is not None and artifact_path.strip():
        return str(Path(artifact_path).expanduser().resolve())
    return str(_latest_json_file(runtime_root / "artifacts"))


def _handle_cutover(args: argparse.Namespace) -> int:
    runtime_root = _resolve_runtime_root(profile=PROFILE_TRIAL, runtime_root=args.runtime_root)
    argv: list[str] = [
        "--mode",
        args.mode,
        "--api-base-url",
        args.api_base_url,
    ]
    if args.auth_token:
        argv.extend(["--auth-token", args.auth_token])
    if args.login_email:
        argv.extend(["--login-email", args.login_email])
    if args.login_password:
        argv.extend(["--login-password", args.login_password])
    resolved_artifact_path = _resolve_cutover_artifact_path(args.mode, runtime_root, args.artifact_path)
    if resolved_artifact_path:
        argv.extend(["--artifact-path", resolved_artifact_path])
    if args.note:
        argv.extend(["--note", args.note])
    if args.skip_preflight:
        argv.append("--skip-preflight")
    return set_pilot_cutover_main(argv)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "up":
            return _handle_up(args)
        if args.command == "check":
            return _handle_check(args)
        if args.command == "demo":
            return _handle_demo(args)
        if args.command == "ask":
            return _handle_ask(args)
        if args.command == "cutover":
            return _handle_cutover(args)
        raise ValueError(f"Unsupported command: {args.command}")
    except Exception as exc:  # noqa: BLE001 - top-level CLI should fail with one concise line
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
