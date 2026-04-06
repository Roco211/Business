from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import Shop
from app.services.audit_logs import append_shop_rules_trial_calibration_audit_log

SUPPORTED_RULE_FIELDS = (
    "low_confidence_threshold",
    "require_price_confirmation",
    "require_new_item_confirmation",
)


class TrialCalibrationApplyError(ValueError):
    """Raised when a calibration artifact cannot be safely applied."""


def _load_calibration_artifact(report_path: str | Path) -> dict[str, Any]:
    resolved_report_path = Path(report_path).resolve()
    try:
        raw_payload = json.loads(resolved_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrialCalibrationApplyError(f"Invalid calibration artifact: {exc}") from exc

    if not isinstance(raw_payload, dict):
        raise TrialCalibrationApplyError("Invalid calibration artifact: root payload must be an object")

    artifact_id = raw_payload.get("artifact_id")
    trial_provider_profile = raw_payload.get("trial_provider_profile")
    recommended_shop_rules = raw_payload.get("recommended_shop_rules")

    if not isinstance(artifact_id, str) or not artifact_id.strip():
        raise TrialCalibrationApplyError("Invalid calibration artifact: artifact_id is required")
    if not isinstance(trial_provider_profile, str) or not trial_provider_profile.strip():
        raise TrialCalibrationApplyError("Invalid calibration artifact: trial_provider_profile is required")
    if not isinstance(recommended_shop_rules, dict) or not recommended_shop_rules:
        raise TrialCalibrationApplyError("Invalid calibration artifact: recommended_shop_rules is required")

    unsupported_fields = [field for field in recommended_shop_rules if field not in SUPPORTED_RULE_FIELDS]
    if unsupported_fields:
        raise TrialCalibrationApplyError(
            f"Invalid calibration artifact: unsupported recommended rule fields: {', '.join(unsupported_fields)}"
        )

    missing_fields = [field for field in SUPPORTED_RULE_FIELDS if field not in recommended_shop_rules]
    if missing_fields:
        raise TrialCalibrationApplyError(
            f"Invalid calibration artifact: missing recommended rule fields: {', '.join(missing_fields)}"
        )

    low_confidence_threshold = recommended_shop_rules["low_confidence_threshold"]
    require_price_confirmation = recommended_shop_rules["require_price_confirmation"]
    require_new_item_confirmation = recommended_shop_rules["require_new_item_confirmation"]

    if isinstance(low_confidence_threshold, bool) or not isinstance(low_confidence_threshold, (int, float)):
        raise TrialCalibrationApplyError("Invalid calibration artifact: low_confidence_threshold must be numeric")
    if not isinstance(require_price_confirmation, bool):
        raise TrialCalibrationApplyError("Invalid calibration artifact: require_price_confirmation must be boolean")
    if not isinstance(require_new_item_confirmation, bool):
        raise TrialCalibrationApplyError(
            "Invalid calibration artifact: require_new_item_confirmation must be boolean"
        )

    normalized_threshold = float(low_confidence_threshold)
    if normalized_threshold < 0.0 or normalized_threshold > 1.0:
        raise TrialCalibrationApplyError("Invalid calibration artifact: low_confidence_threshold must be in [0, 1]")

    return {
        "artifact_id": artifact_id.strip(),
        "trial_provider_profile": trial_provider_profile.strip(),
        "recommended_shop_rules": {
            "low_confidence_threshold": normalized_threshold,
            "require_price_confirmation": require_price_confirmation,
            "require_new_item_confirmation": require_new_item_confirmation,
        },
    }


def _round_threshold_for_storage(value: float) -> Decimal:
    return Decimal(f"{value:.4f}")


def apply_trial_calibration(
    *,
    report_path: str | Path,
    shop_id: str | None = None,
    actor_id: str | None = None,
    db_session=None,
) -> dict[str, Any]:
    artifact = _load_calibration_artifact(report_path)

    settings = get_settings()
    target_shop_id = (shop_id or settings.default_shop_id).strip()
    target_actor_id = (actor_id or settings.default_owner_actor_id).strip()
    if not target_shop_id:
        raise TrialCalibrationApplyError("Target shop_id is required")
    if not target_actor_id:
        raise TrialCalibrationApplyError("Target actor_id is required")

    owns_session = db_session is None
    session = db_session or get_session_factory()()
    try:
        shop = session.get(Shop, target_shop_id)
        if shop is None:
            raise TrialCalibrationApplyError(f"Target shop '{target_shop_id}' does not exist")

        before = {
            "low_confidence_threshold": float(shop.low_confidence_threshold),
            "require_price_confirmation": shop.require_price_confirmation,
            "require_new_item_confirmation": shop.require_new_item_confirmation,
        }

        recommended_rules = artifact["recommended_shop_rules"]
        shop.low_confidence_threshold = _round_threshold_for_storage(recommended_rules["low_confidence_threshold"])
        shop.require_price_confirmation = bool(recommended_rules["require_price_confirmation"])
        shop.require_new_item_confirmation = bool(recommended_rules["require_new_item_confirmation"])
        shop.updated_at = datetime.now(UTC).replace(tzinfo=None)

        after = {
            "low_confidence_threshold": float(shop.low_confidence_threshold),
            "require_price_confirmation": shop.require_price_confirmation,
            "require_new_item_confirmation": shop.require_new_item_confirmation,
        }

        append_shop_rules_trial_calibration_audit_log(
            session,
            shop=shop,
            actor_id=target_actor_id,
            artifact_id=artifact["artifact_id"],
            trial_provider_profile=artifact["trial_provider_profile"],
            before=before,
            after=after,
        )

        if owns_session:
            session.commit()
        else:
            session.flush()

        return {
            "shop_id": shop.shop_id,
            "artifact_id": artifact["artifact_id"],
            "trial_provider_profile": artifact["trial_provider_profile"],
            "applied_rules": after,
        }
    finally:
        if owns_session:
            session.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply machine-readable pilot calibration recommendations to shop runtime rules.",
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to the calibration report JSON artifact.",
    )
    parser.add_argument(
        "--shop-id",
        default=None,
        help="Target shop id. Defaults to DEFAULT_SHOP_ID when omitted.",
    )
    parser.add_argument(
        "--actor-id",
        default=None,
        help="Actor id for audit logging. Defaults to DEFAULT_OWNER_ACTOR_ID when omitted.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = apply_trial_calibration(
            report_path=Path(args.report),
            shop_id=args.shop_id,
            actor_id=args.actor_id,
        )
    except TrialCalibrationApplyError as exc:
        print(f"Apply trial calibration failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
