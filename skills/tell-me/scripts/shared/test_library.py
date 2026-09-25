#!/usr/bin/env python3
"""Unit tests for library.py and serve_library.py (offline; the server test binds 127.0.0.1)."""
import http.server
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from library import INDEX_FILE, entries, last_summarized, root_of, write_index
from render_html import build, write
from save_summary import render
import serve_library
from serve_library import RangeHandler

META = {"id": "abc", "title": "Zeta talk", "channel": "Chan", "webpage_url": "https://www.youtube.com/watch?v=abc",
        "platform": "youtube", "prepared": "2026-09-24", "prepared_at": "2026-09-24T10:00:00", "summary": {"mode": "tldr"}}


def make(root: Path, rel: str, meta: dict, page=True) -> Path:
    folder = root / rel
    folder.mkdir(parents=True)
    (folder / "metadata.json").write_text(json.dumps(meta))
    (folder / "content.md").write_text("x")
    if page:
        (folder / "summary.md").write_text(render(meta, "**TL;DR:** ok", "tldr", "en", "2026-09-25"))
        (folder / "summary.html").write_text("")
    return folder


class TestLibrary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = mock.patch.dict(os.environ, {"TELL_ME_ROOT": str(self.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_entries_only_folders_with_pages(self):
        make(self.root, "videos/youtube/chan/zeta-talk", META)
        make(self.root, "videos/youtube/chan/unsummarized", META | {"id": "x"}, page=False)
        make(self.root, "videos/youtube/other/alpha", {"id": "y", "title": "Alpha", "uploader": "Other", "prepared": "2026-09-20"})
        items = {e["path"]: e for e in entries(self.root)}
        self.assertEqual(set(items), {"videos/youtube/chan/zeta-talk", "videos/youtube/other/alpha"})
        zeta = items["videos/youtube/chan/zeta-talk"]
        self.assertTrue(zeta.pop("summarized"))  # summary.md mtime (no created_at in META)
        self.assertEqual(zeta, {
            "path": "videos/youtube/chan/zeta-talk", "page": "videos/youtube/chan/zeta-talk/summary.html", "title": "Zeta talk",
            "author": "Chan", "source": "video", "type": "video", "group": "videos/youtube/chan", "group_name": "Chan",
            "date": zeta["date"], "kind": "summary", "mode": "tldr"})

    def test_type_is_the_source_or_digest(self):
        make(self.root, "posts/x/a/post-1", {"source": "x", "id": "1", "title": "Post"})
        make(self.root, "documents/papers/tiny", {"source": "file", "id": "s", "title": "Tiny"})
        digest = self.root / "digests" / "2026-09-25-a-and-1-more"
        digest.mkdir(parents=True)
        (digest / "metadata.json").write_text(json.dumps({"kind": "digest", "title": "A and B", "items": []}))
        (digest / "digest.html").write_text("")
        playlist = self.root / "videos" / "youtube" / "chan" / "_digests" / "pl"
        playlist.mkdir(parents=True)
        (playlist / "metadata.json").write_text(json.dumps({"kind": "digest", "title": "PL", "videos": []}))
        (playlist / "digest.html").write_text("")
        types = {e["path"]: e["type"] for e in entries(self.root)}
        self.assertEqual(types, {"posts/x/a/post-1": "x", "documents/papers/tiny": "file",
                                 "digests/2026-09-25-a-and-1-more": "digest",
                                 "videos/youtube/chan/_digests/pl": "digest"})

    def test_sidebar_has_the_source_filter(self):
        from library import SIDEBAR_JS, sidebar_html
        self.assertIn('class="types"', sidebar_html())
        for t in ("video", "web", "github", "x", "hn", "file", "digest"):
            self.assertIn(f"{t}:[", SIDEBAR_JS.replace("'", ""))
        self.assertIn("st.types", SIDEBAR_JS)

    def test_group_per_source(self):
        from library import group_of
        self.assertEqual(group_of("articles/example-com/post", "web", {"site": "Example", "author": "Ann"}),
                         ("articles/example-com", "Example"))
        self.assertEqual(group_of("repos/github/yt-dlp/yt-dlp", "github", {"author": "yt-dlp"}),
                         ("repos/github/yt-dlp", "yt-dlp"))
        self.assertEqual(group_of("discussions/hn/title-1", "hn", {"author": "pg"}), ("", ""))
        self.assertEqual(group_of("videos/youtube", "video", {"author": "x"}), ("", ""))

    def test_start_time_is_folder_creation_time(self):
        from datetime import datetime
        from library import downloaded_at
        folder = make(self.root, "videos/youtube/chan/zeta-talk", META)
        birth = getattr(folder.stat(), "st_birthtime", None)
        if not birth:
            self.skipTest("no folder creation time on this file system")
        self.assertEqual(downloaded_at(folder, META), datetime.fromtimestamp(birth).isoformat(timespec="seconds"))

    def test_start_time_falls_back_without_creation_time(self):
        from library import downloaded_at
        folder = make(self.root, "videos/youtube/chan/zeta-talk", META)
        real = os.stat(folder)
        no_birth = mock.Mock(spec=["st_mtime"], st_mtime=real.st_mtime)
        with mock.patch.object(Path, "stat", lambda self, **kw: no_birth if self == folder else os.stat(self)):
            self.assertEqual(downloaded_at(folder, META), "2026-09-24T10:00:00")  # prepared_at
            self.assertTrue(downloaded_at(folder, {"prepared": "2026-09-20"}).startswith("2026-09-20T"))

    def test_last_summarized_prefers_created_at_and_skips_digests(self):
        self.assertIsNone(last_summarized(self.root))
        make(self.root, "videos/youtube/chan/old", META | {"summary": {"created_at": "2026-09-01T09:00:00"}})
        make(self.root, "videos/youtube/chan/new", META | {"id": "n", "summary": {"created_at": "2026-09-25T09:00:00"}})
        make(self.root, "videos/youtube/chan/_digests/pl", {"kind": "digest", "title": "PL", "summary": {"created_at": "2027-01-01T00:00:00"}})
        (self.root / "videos/youtube/chan/_digests/pl/digest.html").write_text("")
        self.assertEqual(last_summarized(self.root), self.root / "videos/youtube/chan/new/summary.html")

    def test_date_only_summary_does_not_jump_ahead_after_an_edit(self):
        make(self.root, "videos/youtube/chan/timed", META | {"summary": {"created_at": "2026-09-25T09:00:00"}})
        old = make(self.root, "videos/youtube/chan/dateonly", META | {"id": "d", "summary": {"created": "2026-09-25"}})
        (old / "summary.md").write_text((old / "summary.md").read_text())  # fresh mtime (e.g. dates refreshed)
        self.assertEqual(last_summarized(self.root), self.root / "videos/youtube/chan/timed/summary.html")

    def test_index_is_loadable_js(self):
        make(self.root, "videos/youtube/chan/zeta-talk", META)
        text = (write_index(self.root)).read_text()
        self.assertTrue(text.startswith("window.DM_LIBRARY = {"))
        data = json.loads(text[len("window.DM_LIBRARY = "):].rstrip().rstrip(";"))
        self.assertEqual(len(data["items"]), 1)

    def test_page_gets_sidebar_and_relative_root(self):
        folder = make(self.root, "videos/youtube/chan/zeta-talk", META)
        page = build(folder)
        self.assertIn('data-root="../../../.." data-self="videos/youtube/chan/zeta-talk"', page)
        self.assertIn('<script src="../../../../library.js"></script>', page)
        for view in ("tree", "date", "title", "author"):
            self.assertIn(f'data-view="{view}"', page)
        write(folder)
        self.assertTrue((self.root / INDEX_FILE).exists())

    def test_no_sidebar_outside_library(self):
        with tempfile.TemporaryDirectory() as other:
            folder = make(Path(other), "f", META)
            self.assertIsNone(root_of(folder))
            self.assertNotIn('id="lib"', build(folder))

    def test_youtube_player_without_local_video(self):
        folder = make(self.root, "videos/youtube/chan/zeta-talk", META)
        page = build(folder)
        self.assertIn('<div class="frame" data-yt="abc"><img src="https://i.ytimg.com/vi/abc/hqdefault.jpg"', page)
        self.assertNotIn("<video", page)

    def test_non_youtube_player_uses_thumbnail_or_plain_box(self):
        vimeo = {"id": "1", "title": "V", "platform": "vimeo", "webpage_url": "https://vimeo.com/1"}
        self.assertIn('<div class="frame"><a class="play" href="https://vimeo.com/1"', build(make(self.root, "videos/vimeo/u/v", vimeo)))
        page = build(make(self.root, "videos/vimeo/u/w", vimeo | {"thumbnail": "https://i.vimeocdn.com/t.jpg"}))
        self.assertIn('<div class="frame"><img src="https://i.vimeocdn.com/t.jpg"', page)


class TestApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        make(self.root, "videos/youtube/chan/zeta-talk", META)
        self.srv = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), lambda *a, **kw: RangeHandler(*a, directory=str(self.root), **kw))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.tmp.cleanup()

    def call(self, path, body=None, headers=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers=headers or {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def test_status(self):
        self.assertEqual(self.call("/api/status?path=videos/youtube/chan/zeta-talk"), (200, {"status": "none"}))
        folder = self.root / "videos/youtube/chan/zeta-talk"
        (folder / "video.mkv").write_bytes(b"")
        (folder / "metadata.json").write_text(json.dumps(META | {"video_file": "video.mkv", "video_quality": "best"}))
        self.assertEqual(self.call("/api/status?path=videos/youtube/chan/zeta-talk")[1]["status"], "done")

    def test_unknown_or_escaping_paths(self):
        self.assertEqual(self.call("/api/status?path=../../etc")[0], 404)
        self.assertEqual(self.call("/api/status?path=youtube/nope")[0], 404)
        self.assertEqual(self.call("/api/download", {"path": "../x"}, {"X-DM-Summarize": "1"})[0], 404)

    def test_download_needs_header_and_same_host(self):
        self.assertEqual(self.call("/api/download", {"path": "videos/youtube/chan/zeta-talk"})[0], 403)
        self.assertEqual(self.call("/api/download", {"path": "videos/youtube/chan/zeta-talk"},
                                   {"X-DM-Summarize": "1", "Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.call("/api/status?path=videos/youtube/chan/zeta-talk", headers={"Host": "evil.example"})[0], 403)

    def test_download_starts_best_quality_background_job(self):
        real = serve_library.video_cli
        calls = []

        def fake(folder, *args):
            calls.append((folder, args))
            return real(folder, *args) if args == ("--status",) else (0, {"status": "running"})
        with mock.patch("serve_library.video_cli", side_effect=fake):
            code, _ = self.call("/api/download", {"path": "videos/youtube/chan/zeta-talk"}, {"X-DM-Summarize": "1"})
        self.assertEqual(code, 202)
        started = [c for c in calls if "--background" in c[1]]
        self.assertEqual(started, [(self.root / "videos/youtube/chan/zeta-talk",
                                    (META["webpage_url"], "--background", "--quality", "best"))])

    def test_an_x_posts_video_downloads_from_the_post_with_its_item(self):
        rel = "x/someone/1234-a-post"
        make(self.root, rel, {"source": "x", "id": "1234", "title": "A post", "url": "https://x.com/someone/status/1234",
                              "video": {"source_url": "https://x.com/someone/status/1234", "playlist_item": 2,
                                        "webpage_url": "https://x.com/someone/status/1234"}})
        calls = []

        def fake(folder, *args):
            calls.append(args)
            return (0, None) if args == ("--status",) else (0, {"status": "running"})
        with mock.patch("serve_library.video_cli", side_effect=fake):
            self.assertEqual(self.call(f"/api/status?path={rel}")[0], 200)
            self.assertEqual(self.call("/api/download", {"path": rel}, {"X-DM-Summarize": "1"})[0], 202)
        self.assertIn(("https://x.com/someone/status/1234", "--background", "--quality", "best", "--playlist-item", "2"),
                      calls)

    def test_a_folder_without_a_video_is_unknown_to_the_api(self):
        rel = "x/someone/99-no-video"
        make(self.root, rel, {"source": "x", "id": "99", "title": "No video", "url": "https://x.com/someone/status/99"})
        self.assertEqual(self.call(f"/api/status?path={rel}")[0], 404)

    def test_video_cli_failures_become_json_errors(self):
        folder = self.root / "videos/youtube/chan/zeta-talk"
        with mock.patch("serve_library.video_cli", return_value=(1, "boom")):
            self.assertEqual(self.call("/api/status?path=videos/youtube/chan/zeta-talk")[1], {"status": "failed", "error": "boom"})
            code, data = self.call("/api/download", {"path": "videos/youtube/chan/zeta-talk"}, {"X-DM-Summarize": "1"})
        self.assertEqual((code, data["status"]), (202, "failed"))
        with mock.patch("serve_library.VIDEO_CLI", folder / "nope.py"):
            self.assertEqual(serve_library.video_cli(folder, "--status")[0], 2)

    def test_status_comes_from_the_video_cli(self):
        folder = self.root / "videos/youtube/chan/zeta-talk"
        (folder / ".video-download.json").write_text(json.dumps({"status": "failed", "error": "boom"}))
        self.assertEqual(self.call("/api/status?path=videos/youtube/chan/zeta-talk")[1], {"status": "failed", "error": "boom"})

    def test_delete_video_endpoint(self):
        folder = self.root / "videos/youtube/chan/zeta-talk"
        (folder / "video.mkv").write_bytes(b"x" * 2048)
        (folder / "metadata.json").write_text(json.dumps(META | {"video_file": "video.mkv", "video_quality": "best"}))
        page = build(folder)
        self.assertIn('<div class="dl rm" hidden><button type="button">🗑 Delete downloaded video</button>', page)
        self.assertIn("video.mkv, 2 KB", page)
        self.assertEqual(self.call("/api/delete-video", {"path": "videos/youtube/chan/zeta-talk"})[0], 403)  # no header
        code, data = self.call("/api/delete-video", {"path": "videos/youtube/chan/zeta-talk"}, {"X-DM-Summarize": "1"})
        self.assertEqual((code, data), (200, {"status": "none", "deleted": "video.mkv"}))
        self.assertFalse((folder / "video.mkv").exists())
        self.assertIn('data-yt="abc"', (folder / "summary.html").read_text())

    def test_page_has_download_button(self):
        page = build(self.root / "videos/youtube/chan/zeta-talk")
        self.assertIn('<div class="dl" hidden><button type="button">', page)


class TestRangeServer(unittest.TestCase):
    def test_range_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "video.mkv").write_bytes(bytes(range(100)))
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                                  lambda *a, **kw: RangeHandler(*a, directory=tmp, **kw))
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{srv.server_address[1]}/video.mkv"
            try:
                def get(rng=None):
                    req = urllib.request.Request(url, headers={"Range": rng} if rng else {})
                    with urllib.request.urlopen(req) as r:
                        return r.status, r.headers, r.read()
                status, headers, body = get("bytes=10-19")
                self.assertEqual((status, headers["Content-Range"], body), (206, "bytes 10-19/100", bytes(range(10, 20))))
                self.assertEqual(get("bytes=95-")[2], bytes(range(95, 100)))
                self.assertEqual(get("bytes=-3")[2], bytes(range(97, 100)))
                status, headers, body = get()
                self.assertEqual((status, len(body), headers["Accept-Ranges"]), (200, 100, "bytes"))
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
