#!/usr/bin/env python3
"""Unit tests for check_quotes.py (offline)."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import check_quotes
from check_quotes import check, quotes

CONTENT = """## Discussion

- **pg** [→](https://news.ycombinator.com/item?id=2) (depth 0): The hardest part of a startup isn&#x27;t the code, it's
  finding   users who *actually* care. We tried [three ideas](https://x.test/ideas) before one stuck.
- **tptacek** [→](https://news.ycombinator.com/item?id=3) (depth 1, reply to pg): I’d push back — most founders
  know their users; they just don't ship.

[¶4](https://blog.dev/p#:~:text=Memory%20safety) Memory safety bugs are 70% of the CVEs we fix.
"""


class TestQuotes(unittest.TestCase):
    def test_finds_quotes_of_three_words_or_more_outside_code(self):
        body = ('> "finding users who actually care" (**pg**)\n'
                'The "gist" of it, “most founders know their users”.\n'
                '`"not a quote at all here"`\n```\n"nor this one here"\n```')
        self.assertEqual(quotes(body), ["finding users who actually care", "most founders know their users"])

    def test_attributed_quote_with_quotes_inside_stays_whole(self):
        body = ('> "I\'d push back — most "founders" know their users" (**tptacek**, [→](x)) and '
                '"finding users who actually care" (**pg**, [→](y)), "three ideas before one stuck"')
        self.assertEqual(quotes(body), ['I\'d push back — most "founders" know their users',
                                        "finding users who actually care", "three ideas before one stuck"])
        self.assertEqual(len(check(body, CONTENT)["missing"]), 1)  # "founders" is not quoted in the source

    def test_an_inch_mark_does_not_hide_the_next_quote(self):
        body = 'A 12" record and "the hardest part of a startup" said pg; also "an invented quote here".'
        self.assertEqual(quotes(body), ["the hardest part of a startup", "an invented quote here"])
        self.assertEqual(check(body, CONTENT)["missing"], ["an invented quote here"])

    def test_a_quote_wrapped_over_two_lines_is_checked(self):
        body = 'He wrote "most founders know their\nusers; they just ship fast" (**tptacek**)\n\n- "next item here"'
        self.assertEqual(quotes(body), ["most founders know their users; they just ship fast", "next item here"])
        self.assertEqual(len(check(body, CONTENT)["missing"]), 2)

    def test_markdown_escapes_are_ignored(self):
        content = "Use snake\\_case names and 2\\*3 math in *every* file."
        self.assertEqual(check('"use snake_case names and 2*3 math"', content)["missing"], [])

    def test_two_quotes_on_one_line(self):
        body = '- "4D dynamical worlds": jargon? One side: > "sounds overhyped / scammy" (**etwigg**, [→](x))'
        self.assertEqual(quotes(body), ["sounds overhyped / scammy", "4D dynamical worlds"])

    def test_real_quotes_pass_whatever_the_formatting(self):
        body = ('"The hardest part of a startup isn\'t the code" and "we tried three ideas before one stuck." and '
                '“I\'d push back - most founders know their users” and "Memory safety bugs are 70%"')
        out = check(body, CONTENT)
        self.assertEqual((out["checked"], out["missing"]), (4, []))

    def test_invented_quote_is_flagged(self):
        out = check('"users never care about code" but "finding users who actually care"', CONTENT)
        self.assertEqual(out["missing"], ["users never care about code"])

    def test_ellipsis_parts_must_appear_in_order(self):
        self.assertEqual(check('"The hardest part ... finding users who actually care"', CONTENT)["missing"], [])
        self.assertEqual(check('"The hardest part […] finding users"', CONTENT)["missing"], [])
        out = check('"finding users who actually care … The hardest part of a startup"', CONTENT)
        self.assertEqual(len(out["missing"]), 1)

    def test_quote_across_two_comments_is_not_verbatim(self):
        self.assertEqual(len(check('"before one stuck. tptacek I\'d push back"', CONTENT)["missing"]), 1)


class TestMain(unittest.TestCase):
    def test_folder_content_file_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "metadata.json").write_text(json.dumps({"source": "hn", "content_file": "content.md"}))
            (folder / "content.md").write_text(CONTENT)
            out = io.StringIO()
            with mock.patch("sys.stdin", io.StringIO('"users never care about code"')), \
                    mock.patch.object(check_quotes, "log") as log, redirect_stdout(out):
                self.assertEqual(check_quotes.main([tmp]), 1)
            self.assertEqual(json.loads(out.getvalue())["missing"], ["users never care about code"])
            self.assertIn("NOT FOUND: users never care about code", log.call_args.args[0])
            (folder / "summary.md").write_text('"most founders know their users"')
            with mock.patch.object(check_quotes, "log"), redirect_stdout(io.StringIO()):
                self.assertEqual(check_quotes.main([tmp, "--summary"]), 0)


if __name__ == "__main__":
    unittest.main()
