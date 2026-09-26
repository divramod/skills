# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["supertonic==1.3.1"]
# ///
"""Text file -> WAV with Supertonic-3 (local ONNX text-to-speech, 31 languages, CPU). Run by speak.py via
`uv run --script`, which installs the pinned package into uv's cache; the model (~385 MB, Hugging Face
Supertone/supertonic-3) downloads on first use into $SUPERTONIC_CACHE_DIR.

Paragraphs are synthesized one by one (a pause after each). stdout gets `PARTS <n>` first, then `PART <i> <percent>`
after each; with --parts DIR each paragraph is also written as DIR/<i>.wav right away (i from 1), so a page can play
the start while the rest is still being made. The output is exactly those parts joined. Unknown languages are read
with the language-neutral voice ("na").

Usage: tts_supertonic.py <text-file> <out.wav> [--parts DIR] [--lang en] [--voice F1] [--steps 8] [--speed 1.05]
       tts_supertonic.py --warm   (download the model and exit)
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from supertonic import TTS
from supertonic.config import AVAILABLE_LANGUAGES, UNKNOWN_LANGUAGE

PAUSE = 0.6  # seconds of silence between paragraphs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--voice", default="F1")
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--speed", type=float, default=1.05)
    ap.add_argument("--parts", help="also write each paragraph to PARTS/<i>.wav as soon as it is ready")
    ap.add_argument("--warm", action="store_true")
    args = ap.parse_args()
    tts = TTS(auto_download=True)
    if args.warm:
        print(f"model ready: {tts.model_dir}")
        return 0
    if args.voice not in tts.voice_style_names:
        print(f"unknown voice {args.voice}; one of {', '.join(tts.voice_style_names)}", file=sys.stderr)
        return 1
    lang = (args.lang or "").lower().split("-")[0]
    lang = lang if lang in AVAILABLE_LANGUAGES else UNKNOWN_LANGUAGE
    style = tts.get_voice_style(voice_name=args.voice)
    with open(args.text, encoding="utf-8") as f:
        paragraphs = [p.strip() for p in f.read().split("\n\n") if p.strip()]
    if not paragraphs:
        print("nothing to read", file=sys.stderr)
        return 1
    total, done, parts = sum(len(p) for p in paragraphs), 0, []
    silence = np.zeros((1, int(tts.sample_rate * PAUSE)), dtype=np.float32)
    print(f"PARTS {len(paragraphs)}", flush=True)
    for i, p in enumerate(paragraphs, 1):
        wav, _ = tts.synthesize(p, voice_style=style, lang=lang, total_steps=args.steps, speed=args.speed)
        part = wav.reshape(1, -1) if i == len(paragraphs) else np.concatenate([wav.reshape(1, -1), silence], axis=1)
        parts.append(part)
        if args.parts:
            tmp = os.path.join(args.parts, f".{i}.tmp.wav")
            tts.save_audio(part, tmp)
            os.replace(tmp, os.path.join(args.parts, f"{i}.wav"))  # a page never loads half a file
        done += len(p)
        print(f"PART {i} {100 * done / total:.1f}", flush=True)
    tts.save_audio(np.concatenate(parts, axis=1), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
