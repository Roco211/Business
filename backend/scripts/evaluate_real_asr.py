from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.asr_provider_eval import AsrProviderEvalSummary, evaluate_asr_provider
from app.services.asr_types import AsrProviderError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the configured ASR gateway with a local audio file.",
    )
    parser.add_argument(
        "audio_path",
        help="Path to a local audio file to evaluate.",
    )
    parser.add_argument(
        "--media-id",
        default=None,
        help="Optional media ID override. In mock mode, use a fixture ID like voice_query_demo.",
    )
    parser.add_argument(
        "--text-hint",
        default=None,
        help="Optional transcript hint to pass through the ASR gateway.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = evaluate_asr_provider(
            audio_path=Path(args.audio_path),
            media_id=args.media_id,
            text_hint=args.text_hint,
        )
    except (AsrProviderError, FileNotFoundError, OSError, NotImplementedError) as exc:
        print(f"ASR evaluation failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
