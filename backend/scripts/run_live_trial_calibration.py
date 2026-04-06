from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.pilot_calibration import ManifestValidationError, run_pilot_calibration
from app.services.asr_types import AsrProviderError
from app.services.ocr_types import OcrProviderError
from app.services.vision_types import VisionProviderError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run pilot calibration across ASR, OCR, and Vision using a tracked manifest.",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to the calibration manifest JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for calibration report artifacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_pilot_calibration(
            manifest_path=Path(args.manifest),
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
    except (
        ManifestValidationError,
        AsrProviderError,
        OcrProviderError,
        VisionProviderError,
        FileNotFoundError,
        OSError,
    ) as exc:
        print(f"Pilot calibration failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
