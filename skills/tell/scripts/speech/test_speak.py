#!/usr/bin/env python3
"""Unit tests for speak.py (offline: a fake engine stands in for Supertonic)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

import speak
from _common import SkillError
from save_summary import render
from speech_text import speech_text, text_hash

META = {"source": "web", "id": "u", "title": "Post", "url": "https://a.b/post", "author": "Ann",
        "content_file": "content.md"}
BODY = "**TL;DR:** short.\n\n## Key points\n\n- one\n- two\n\n## Links\n\n- [x](https://x.y)"

# Writes a silent WAV per paragraph like tts_supertonic.py, and the joined file; records its arguments.
FAKE_ENGINE = r'''
import os, sys, wave
args = sys.argv[1:]
text, out = args[0], args[1]
parts = args[args.index("--parts") + 1]
open(os.path.join(os.path.dirname(out), "engine-args.txt"), "w").write(" ".join(args[2:]))
paragraphs = [p for p in open(text, encoding="utf-8").read().split("\n\n") if p.strip()]
def silent(path):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b"\0\0" * 800)
print(f"PARTS {len(paragraphs)}", flush=True)
for i, _ in enumerate(paragraphs, 1):
    silent(os.path.join(parts, f"{i}.wav"))
    print(f"PART {i} {100 * i / len(paragraphs):.1f}", flush=True)
silent(out)
'''

_home = tempfile.TemporaryDirectory()
_env = mock.patch.dict(os.environ, {"HOME": _home.name})


def setUpModule():
    _env.start()


def tearDownModule():
    _env.stop()
    _home.cleanup()


class SpeakTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "metadata.json").write_text(json.dumps(META))
        (self.dir / "content.md").write_text("# Post\n\nHello")
        (self.dir / "summary.md").write_text(render(META, BODY, "summary", "de", "2026-09-26"))
        fake = self.dir / "fake_engine.py"
        fake.write_text(FAKE_ENGINE)
        self.patches = [mock.patch.object(speak, "engine_cmd", lambda *a: [sys.executable, str(fake), *a]),
                        mock.patch.object(speak, "require", lambda *t: None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def meta(self):
        return json.loads((self.dir / "metadata.json").read_text())


class TestRecord(SpeakTest):
    def test_records_without_ffmpeg_as_wav_and_rerenders_the_page(self):
        with mock.patch.object(speak.shutil, "which", lambda t: None):
            audio = speak.record(self.dir, "M2", None)
        self.assertEqual(audio, self.dir / "summary.wav")
        meta = self.meta()
        self.assertEqual(meta["speech_file"], "summary.wav")
        self.assertEqual(meta["speech_voice"], "M2")
        self.assertEqual(meta["speech_hash"], text_hash(speech_text((self.dir / "summary.md").read_text())))
        self.assertEqual((self.dir / "engine-args.txt").read_text().split()[-4:], ["--lang", "de", "--voice", "M2"])
        for gone in (speak.STATUS_FILE, speak.PARTS_DIR, ".speech.txt", ".summary.speech.wav"):
            self.assertFalse((self.dir / gone).exists(), gone)
        self.assertIn('<audio controls preload="none" src="summary.wav">', (self.dir / "summary.html").read_text())
        self.assertEqual(speak.status(self.dir), {"status": "done", "audio": "summary.wav"})

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_ffmpeg_compresses_to_m4a_and_replaces_an_old_wav(self):
        (self.dir / "summary.wav").write_bytes(b"old")
        audio = speak.record(self.dir, "F1", "en")
        self.assertEqual(audio.name, "summary.m4a")
        self.assertGreater(audio.stat().st_size, 0)
        self.assertFalse((self.dir / "summary.wav").exists())

    def test_engine_failure_is_recorded(self):
        with mock.patch.object(speak, "engine_cmd", lambda *a: [sys.executable, "-c", "import sys; sys.exit('boom')"]):
            with self.assertRaises(SkillError):
                speak.record(self.dir, "F1", None)
        state = speak.status(self.dir)
        self.assertEqual(state["status"], "failed")
        self.assertIn("boom", state["error"])
        self.assertFalse((self.dir / speak.PARTS_DIR).exists())


class TestStatus(SpeakTest):
    def test_none_done_stale(self):
        self.assertEqual(speak.status(self.dir), {"status": "none"})
        with mock.patch.object(speak.shutil, "which", lambda t: None):
            speak.record(self.dir, "F1", None)
        self.assertEqual(speak.status(self.dir)["status"], "done")
        note = self.dir / "summary.md"
        note.write_text(note.read_text().replace("short", "changed"))
        self.assertEqual(speak.status(self.dir)["status"], "stale")

    def test_running_and_dead_process(self):
        (self.dir / speak.STATUS_FILE).write_text(json.dumps({"status": "running", "pid": os.getpid(), "parts": 2,
                                                             "total": 5, "progress": 40.0}))
        self.assertEqual(speak.status(self.dir), {"status": "running", "progress": 40.0, "parts": 2, "total": 5,
                                                  "parts_dir": speak.PARTS_DIR})
        (self.dir / speak.STATUS_FILE).write_text(json.dumps({"status": "running", "pid": 2 ** 22 + 12345}))
        self.assertEqual(speak.status(self.dir)["status"], "failed")

    def test_background_does_not_restart_a_current_recording(self):
        with mock.patch.object(speak.shutil, "which", lambda t: None):
            speak.record(self.dir, "F1", None)
        with mock.patch.object(speak.subprocess, "Popen") as popen:
            self.assertEqual(speak.start_background(self.dir, None, None)["status"], "done")
        popen.assert_not_called()

    def test_needs_a_saved_note(self):
        (self.dir / "summary.md").unlink()
        with self.assertRaises(SkillError):
            speak.start_background(self.dir, None, None)


if __name__ == "__main__":
    unittest.main()
