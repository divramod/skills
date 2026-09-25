#!/usr/bin/env python3
"""Table test for route.py (offline)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _common import SkillError
from route import route

CASES = [
    # input -> (source, kind, id)
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", ("video", "video", "dQw4w9WgXcQ")),
    ("https://youtu.be/dQw4w9WgXcQ?si=abc", ("video", "video", "dQw4w9WgXcQ")),
    ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", ("video", "video", "dQw4w9WgXcQ")),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", ("video", "video", "dQw4w9WgXcQ")),
    ("https://www.youtube.com/live/dQw4w9WgXcQ", ("video", "video", "dQw4w9WgXcQ")),
    ("youtube.com/watch?v=dQw4w9WgXcQ", ("video", "video", "dQw4w9WgXcQ")),
    ("https://www.youtube.com/playlist?list=PL123", ("video", "playlist", "PL123")),
    ("https://www.youtube.com/@aidotengineer", ("video", "channel", "@aidotengineer")),
    ("https://www.youtube.com/@aidotengineer/videos", ("video", "channel", "@aidotengineer")),
    ("https://vimeo.com/76979871", ("video", "video", "https://vimeo.com/76979871")),
    ("https://www.tiktok.com/@user/video/7312345678901234567", ("video", "video", None)),
    ("https://podcasts.apple.com/us/podcast/x/id123?i=456", ("video", "video", None)),
    ("https://example.com/talk.mp4", ("video", "video", None)),
    ("https://x.com/jack/status/20", ("x", "post", "20")),
    ("https://twitter.com/jack/status/20?s=20", ("x", "post", "20")),
    ("https://fixupx.com/jack/status/20/photo/1", ("x", "post", "20")),
    ("https://vxtwitter.com/jack/status/20", ("x", "post", "20")),
    ("https://x.com/i/web/status/20", ("x", "post", "20")),
    ("https://news.ycombinator.com/item?id=1", ("hn", "item", "1")),
    ("https://www.reddit.com/r/programming/comments/1wexekt/data_races/", ("reddit", "post", "1wexekt")),
    ("https://old.reddit.com/r/Python/comments/1ABC/x/?utm_source=share", ("reddit", "post", "1abc")),
    ("https://new.reddit.com/r/programming/comments/1wexekt/x/p9is1t8/?context=3", ("reddit", "comment", "1wexekt")),
    ("https://reddit.com/comments/1wexekt", ("reddit", "post", "1wexekt")),
    ("https://redd.it/1wexekt", ("reddit", "post", "1wexekt")),
    ("https://www.reddit.com/r/programming/s/AbC123", ("reddit", "share", "share/AbC123")),
    ("https://www.reddit.com/link/1abc/video/xyz/player", ("video", "video", None)),
    ("https://v.redd.it/xyz", ("video", "video", None)),
    ("https://github.com/yt-dlp/yt-dlp", ("github", "repo", "yt-dlp/yt-dlp")),
    ("https://github.com/yt-dlp/yt-dlp.git", ("github", "repo", "yt-dlp/yt-dlp")),
    ("https://github.com/yt-dlp/yt-dlp/tree/master/yt_dlp", ("github", "repo", "yt-dlp/yt-dlp")),
    ("https://github.com/yt-dlp/yt-dlp/blob/master/README.md#usage", ("github", "blob", "yt-dlp/yt-dlp")),
    ("https://github.com/yt-dlp/yt-dlp/issues/123", ("github", "issue", "yt-dlp/yt-dlp#123")),
    ("https://github.com/yt-dlp/yt-dlp/pull/9", ("github", "pull", "yt-dlp/yt-dlp#9")),
    ("https://github.com/orgs/community/discussions/5", ("web", "page", None)),
    ("https://github.com/community/community/discussions/5", ("github", "discussion", "community/community#5")),
    ("https://github.com/yt-dlp", ("web", "page", None)),
    ("https://github.com/topics/python", ("web", "page", None)),
    ("https://news.ycombinator.com/news", ("web", "page", None)),
    ("https://example.com/blog/post?utm_source=x&page=2#comments", ("web", "page", "https://example.com/blog/post?page=2")),
    ("http://www.example.com", ("web", "page", "https://example.com/")),
    ("https://arxiv.org/pdf/1706.03762.pdf", ("file", "pdf", None)),
    ("https://archive.org/details/some-lecture", ("video", "video", None)),
    ("https://archive.org/details/book/book.pdf", ("file", "pdf", None)),
    ("https://example.edu/files/syllabus.doc", ("file", "doc", None)),  # textutil (macOS) converts it
    ("https://example.edu/files/lecture.ppt", ("web", "page", None)),  # no converter reads .ppt: not a document
    ("https://web.archive.org/web/2020/https://example.com/post", ("web", "page", None)),
    ("https://www.instagram.com/p/Cabc123/", ("video", "video", None)),
    ("https://www.instagram.com/photographer", ("web", "page", None)),
    ("https://www.facebook.com/watchparty/1", ("web", "page", None)),
    ("https://www.ted.com/talks/some_talk", ("video", "video", None)),
    ("https://www.ted.com/read/some-article", ("web", "page", None)),
]


class TestRoute(unittest.TestCase):
    def test_table(self):
        for text, (source, kind, rid) in CASES:
            with self.subTest(text):
                r = route(text)
                self.assertEqual((r["source"], r["kind"]), (source, kind))
                if rid:
                    self.assertEqual(r["id"], rid)
                self.assertTrue(r.get("url") or r.get("path"))

    def test_github_folder_link_keeps_its_path(self):
        r = route("https://github.com/yt-dlp/yt-dlp/tree/master/yt_dlp/extractor")
        self.assertEqual((r["url"], r["ref"], r["path"]),
                         ("https://github.com/yt-dlp/yt-dlp/tree/master/yt_dlp/extractor", "master", "yt_dlp/extractor"))
        self.assertEqual(route(r["url"])["path"], "yt_dlp/extractor")  # shared/prepare.py passes the url on

    def test_github_ref_path_is_kept_whole_for_slashed_refs(self):
        r = route("https://github.com/o/r/blob/feature/x/src/a%20b.py")
        self.assertEqual((r["kind"], r["ref"], r["path"], r["ref_path"]),
                         ("blob", "feature", "x/src/a b.py", "feature/x/src/a b.py"))  # github/prepare.py splits it
        self.assertNotIn("ref_path", route("https://github.com/o/r"))

    def test_github_names_are_validated(self):
        for bad in ("https://github.com/o/..", "https://github.com/o/.", "https://github.com/o%20x/r",
                    "https://github.com/o/r@x/issues/1", "https://github.com/o/.git"):
            with self.subTest(bad), self.assertRaisesRegex(SkillError, "not a GitHub owner or repo name"):
                route(bad)
        self.assertEqual(route("https://github.com/o.x/r_y-z.js")["id"], "o.x/r_y-z.js")

    def test_web_url_is_kept_as_given(self):
        r = route("http://localhost:8000/doc#/route?utm_source=x")
        self.assertEqual(r["url"], "http://localhost:8000/doc#/route?utm_source=x")
        self.assertEqual(r["id"], "https://localhost:8000/doc#/route")  # a route is the page, tracking is not

    def test_fragment_dropped_unless_route(self):
        self.assertEqual(route("https://docsify.js.org/#/quickstart")["id"], "https://docsify.js.org/#/quickstart")
        self.assertEqual(route("https://old.app/#!/a")["id"], "https://old.app/#!/a")
        self.assertEqual(route("https://blog.dev/post#section-2")["id"], "https://blog.dev/post")
        self.assertEqual(route("https://docsify.js.org/#/")["id"], route("https://docsify.js.org/")["id"])
        self.assertEqual(route("https://a.app/#/q?id=3&utm_source=x")["id"], "https://a.app/#/q?id=3")

    def test_query_kept_byte_for_byte_minus_tracking(self):
        self.assertEqual(route("https://a.dev/p?flag&path=%2Fx/y&utm_source=rss&b=1")["id"],
                         "https://a.dev/p?flag&path=%2Fx/y&b=1")
        self.assertEqual(route("https://a.dev/p?utm_%73ource=x&fbclid=1")["id"], "https://a.dev/p")

    def test_canonical_urls(self):
        self.assertEqual(route("https://youtu.be/dQw4w9WgXcQ")["url"], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(route("https://twitter.com/jack/status/20?s=20")["url"], "https://x.com/jack/status/20")
        self.assertEqual(route("https://github.com/o/r/pulls/3")["url"], "https://github.com/o/r/pull/3")

    def test_local_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp).resolve()
            doc = tmp / "paper.pdf"
            doc.write_bytes(b"%PDF")
            (tmp / "notes.md").write_text("# hi")
            (tmp / "clip.mp4").write_bytes(b"")
            for text in (str(doc), doc.as_uri(), "paper.pdf", "./paper.pdf"):
                with self.subTest(text):
                    self.assertEqual(route(text, cwd=tmp), {"source": "file", "kind": "pdf", "id": str(doc), "path": str(doc)})
            self.assertEqual(route("notes.md", cwd=tmp)["kind"], "md")
            self.assertEqual(route("clip.mp4", cwd=tmp)["source"], "video")
            self.assertEqual(route("../" + tmp.name + "/notes.md", cwd=tmp)["path"], str(tmp / "notes.md"))
            with self.assertRaises(SkillError):
                route("missing.pdf", cwd=tmp)
            with self.assertRaises(SkillError):
                route(str(tmp), cwd=tmp)

    def test_home_path(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": tmp}):
            (Path(tmp) / "doc.docx").write_bytes(b"")
            self.assertEqual(route("~/doc.docx")["path"], str((Path(tmp) / "doc.docx").resolve()))

    def test_rejects(self):
        for text in ("", "ftp://example.com/x", "mailto:a@b.c", "https://x.com/jack", "just some words",
                     "https://www.reddit.com/r/programming/", "https://www.reddit.com/user/bob"):
            with self.subTest(text):
                with self.assertRaises(SkillError):
                    route(text)


if __name__ == "__main__":
    unittest.main()
