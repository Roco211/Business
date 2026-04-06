from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.vision_provider_eval import evaluate_vision_file
from app.services.vision_types import VisionProviderError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the configured vision gateway with a local image file.",
    )
    parser.add_argument(
        "image_path",
        help="Path to a local product image to evaluate.",
    )
    return parser


def _infer_content_type(image_path: Path) -> str:
    guessed_content_type, _ = mimetypes.guess_type(image_path.name)
    return guessed_content_type or "application/octet-stream"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    image_path = Path(args.image_path)
    try:
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        result = evaluate_vision_file(
            file_name=image_path.name,
            content_type=_infer_content_type(image_path),
            image_bytes=image_path.read_bytes(),
        )
    except (VisionProviderError, FileNotFoundError, OSError) as exc:
        print(f"Vision evaluation failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
