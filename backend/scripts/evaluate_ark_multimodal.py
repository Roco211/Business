from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import struct
import subprocess
import time
import wave
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import httpx

from app.services.ark_multimodal_provider import ARK_CHAT_COMPLETIONS_URL
from app.services.asr_types import AsrMediaInput
from app.services.asr_gateway import build_asr_gateway
from app.services.ocr_gateway import build_ocr_gateway
from app.services.ocr_types import OcrMediaInput
from app.services.vision_gateway import build_vision_gateway
from app.services.vision_types import VisionMediaInput
from app.core.config import get_settings

DEFAULT_MODEL = "doubao-seed-2-0-pro-260215"


def _now_ms() -> float:
    return time.perf_counter() * 1000


def _run_case(name: str, fn: Callable[[], dict[str, Any]], repeats: int) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for index in range(repeats):
        start = _now_ms()
        try:
            result = fn()
            elapsed = _now_ms() - start
            samples.append({"index": index + 1, "ok": True, "elapsed_ms": round(elapsed, 2), **result})
        except Exception as exc:  # noqa: BLE001 - benchmark must record provider failures
            elapsed = _now_ms() - start
            samples.append(
                {
                    "index": index + 1,
                    "ok": False,
                    "elapsed_ms": round(elapsed, 2),
                    "error_type": type(exc).__name__,
                    "error": _sanitize(str(exc)),
                }
            )
    ok_samples = [sample for sample in samples if sample["ok"]]
    elapsed_values = [sample["elapsed_ms"] for sample in ok_samples]
    confidences = [sample["confidence"] for sample in ok_samples if isinstance(sample.get("confidence"), int | float)]
    return {
        "name": name,
        "success_count": len(ok_samples),
        "failure_count": len(samples) - len(ok_samples),
        "success_rate": round(len(ok_samples) / len(samples), 4) if samples else 0,
        "latency_ms": {
            "min": round(min(elapsed_values), 2) if elapsed_values else None,
            "avg": round(statistics.mean(elapsed_values), 2) if elapsed_values else None,
            "max": round(max(elapsed_values), 2) if elapsed_values else None,
        },
        "confidence": {
            "avg": round(statistics.mean(confidences), 4) if confidences else None,
            "min": round(min(confidences), 4) if confidences else None,
            "max": round(max(confidences), 4) if confidences else None,
        },
        "samples": samples,
    }


def _sanitize(text: str) -> str:
    for key_name in ("ARK_API_KEY", "OCR_PROVIDER_API_KEY", "VISION_PROVIDER_API_KEY", "ASR_PROVIDER_API_KEY", "LLM_PROVIDER_API_KEY"):
        value = os.getenv(key_name)
        if value:
            text = text.replace(value, "[REDACTED]")
    return text


def _generate_receipt_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    font = "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    text_lines = [
        "PURCHASE RECEIPT",
        "M8 SCREW 20 BOX 8.50",
        "HAMMER 2 PCS 35.00",
        "TOTAL 240.00",
    ]
    vf = "drawbox=x=40:y=40:w=720:h=420:color=black:t=3"
    y = 80
    for line in text_lines:
        escaped = line.replace(":", "\\:").replace("'", "\\'")
        vf += f",drawtext=fontfile={font}:text='{escaped}':fontcolor=black:fontsize=36:x=80:y={y}"
        y += 85
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=white:s=800x500:d=1",
            "-frames:v",
            "1",
            "-vf",
            vf,
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _generate_tone_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    framerate = 16000
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(framerate)
        for i in range(framerate):
            value = int(8000 * math.sin(2 * math.pi * 440 * i / framerate))
            wav.writeframes(struct.pack("<h", value))


def _text_llm_case(api_key: str, api_url: str, model: str) -> dict[str, Any]:
    response = httpx.post(
        api_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "你是AI模型连通性测试器，只返回JSON。"},
                {"role": "user", "content": '只返回 {"ok":true,"confidence":0.99,"capability":"text"}'},
            ],
            "temperature": 0.1,
            "max_tokens": 200,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    return {"preview": content[:120], "confidence": 0.99, "usage": payload.get("usage")}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Business AI model providers without exposing secrets.")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", default="docs/ai_model_performance/ark_multimodal_report.json")
    args = parser.parse_args()

    api_key = os.getenv("ARK_API_KEY") or os.getenv("OCR_PROVIDER_API_KEY") or os.getenv("VISION_PROVIDER_API_KEY") or os.getenv("ASR_PROVIDER_API_KEY")
    if not api_key:
        raise SystemExit("ARK_API_KEY or provider-specific API key is required")

    model = os.getenv("ARK_MULTIMODAL_MODEL", DEFAULT_MODEL)
    # Force real Ark providers for this benchmark. backend/.env may intentionally
    # keep local-demo mock providers, but performance evaluation must not use them.
    os.environ["OCR_PROVIDER"] = "volcano"
    os.environ["OCR_PROVIDER_API_URL"] = ARK_CHAT_COMPLETIONS_URL
    os.environ["OCR_PROVIDER_API_KEY"] = api_key
    os.environ["OCR_PROVIDER_MODEL"] = model
    os.environ["OCR_TIMEOUT_SECONDS"] = "60"
    os.environ["OCR_ALLOW_MOCK_FALLBACK"] = "0"
    os.environ["VISION_PROVIDER"] = "volcano"
    os.environ["VISION_PROVIDER_API_URL"] = ARK_CHAT_COMPLETIONS_URL
    os.environ["VISION_PROVIDER_API_KEY"] = api_key
    os.environ["VISION_PROVIDER_MODEL"] = model
    os.environ["VISION_TIMEOUT_SECONDS"] = "60"
    os.environ["VISION_ALLOW_MOCK_FALLBACK"] = "0"
    os.environ["ASR_PROVIDER"] = "volcano"
    os.environ["ASR_PROVIDER_API_URL"] = ARK_CHAT_COMPLETIONS_URL
    os.environ["ASR_PROVIDER_API_KEY"] = api_key
    os.environ["ASR_PROVIDER_MODEL"] = model
    os.environ["ASR_TIMEOUT_SECONDS"] = "60"
    os.environ["ASR_ALLOW_MOCK_FALLBACK"] = "0"

    artifact_dir = Path("/tmp/business_ai_model_eval")
    receipt_path = artifact_dir / "receipt.png"
    audio_path = artifact_dir / "tone.wav"
    _generate_receipt_png(receipt_path)
    _generate_tone_wav(audio_path)

    settings = get_settings()
    ocr_gateway = build_ocr_gateway(settings)
    vision_gateway = build_vision_gateway(settings)
    asr_gateway = build_asr_gateway(settings)
    image_bytes = receipt_path.read_bytes()
    audio_bytes = audio_path.read_bytes()

    cases = [
        _run_case(
            "ark_text_chat",
            lambda: _text_llm_case(api_key, ARK_CHAT_COMPLETIONS_URL, os.getenv("ARK_MULTIMODAL_MODEL", DEFAULT_MODEL)),
            args.repeats,
        ),
        _run_case(
            "ocr_purchase_receipt",
            lambda: _ocr_case(ocr_gateway, image_bytes),
            args.repeats,
        ),
        _run_case(
            "vision_product_recognition",
            lambda: _vision_case(vision_gateway, image_bytes),
            args.repeats,
        ),
        _run_case(
            "asr_transcription",
            lambda: _asr_case(asr_gateway, audio_bytes),
            args.repeats,
        ),
    ]

    report = {
        "generated_at_epoch": round(time.time(), 3),
        "provider": "volcano-ark",
        "model": os.getenv("ARK_MULTIMODAL_MODEL", DEFAULT_MODEL),
        "api_url": ARK_CHAT_COMPLETIONS_URL,
        "api_key_configured": True,
        "secrets_redacted": True,
        "artifacts": {"receipt_png": str(receipt_path), "tone_wav": str(audio_path)},
        "cases": cases,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _ocr_case(gateway: Any, image_bytes: bytes) -> dict[str, Any]:
    result = gateway.extract_purchase_receipt(
        OcrMediaInput("eval_receipt", None, "image/png", "receipt.png", image_bytes=image_bytes)
    )
    item_confidence = result.raw_payload.get("confidence") if isinstance(result.raw_payload, dict) else None
    return {
        "confidence": item_confidence if isinstance(item_confidence, int | float) else None,
        "item_count": len(result.line_items),
        "items": [asdict(item) for item in result.line_items],
        "total_amount": result.total_amount,
        "raw_text_preview": (result.raw_text or "")[:160],
    }


def _vision_case(gateway: Any, image_bytes: bytes) -> dict[str, Any]:
    result = gateway.recognize_product(
        VisionMediaInput("eval_product", None, "image/png", "receipt.png", image_bytes=image_bytes)
    )
    best = result.candidates[0]
    return {
        "confidence": best.confidence,
        "candidate_count": len(result.candidates),
        "candidates": [asdict(candidate) for candidate in result.candidates[:5]],
    }


def _asr_case(gateway: Any, audio_bytes: bytes) -> dict[str, Any]:
    result = gateway.transcribe(
        AsrMediaInput(
            media_ids=["eval_audio"],
            text_hint="请转写音频。测试音频可能是无语音的正弦波，如果没有人声请返回空文本并降低置信度。",
            file_name="tone.wav",
            content_type="audio/wav",
            audio_bytes=audio_bytes,
        )
    )
    return {"confidence": result.confidence, "text_preview": result.text[:160]}


if __name__ == "__main__":
    main()
