# Review of e9c33e2 (2026-09-25): request changes

Files: skills/tell-me/scripts/shared/{panels,library,render_html,serve_library}.py

## Important
1. The chips are never hidden: `#lib .types{display:flex}` overrides `[hidden]`. Add `#lib .types[hidden]{display:none}`. In renderChips(), set `st.types=[]` when fewer than 2 types exist. Never filter out items whose type is unknown (or add an "Other" chip). The same `[hidden]` problem exists for `.dl` (Download/Delete rows): add `.dl[hidden]{display:none}`.
2. The x video player's Delete/Download fail: serve_library `_folder()` needs a top-level `webpage_url`, but x keeps it at `meta.video.webpage_url`. Also pass `--playlist-item`. Alternatively, render the x player with no buttons. Gate the x player on `meta.get("video")`, not on `video_file`.
3. `link()` does not check the scheme. An HN `article_url` of `javascript:` gets through. Allow only http(s), plus the relative original_file (keep its exists() check). Add a test.
4. Unexpected metadata crashes build(): labels containing None, `release` as a string, `stars` as "1,234", posts/size/word_count as strings, `extras` as a string. `num()` should return None for non-numbers; add type checks; wrap `panel(...)` in build() so a failure logs and renders an empty panel.

## Suggestions
- HN panel: show "text post" only when points/comments are present.
- Pluralize "in 1 files" and fix the test to match.
- Accept `languages` given as a dict (top 3 keys).
- esc() changed_files, posts and threads.
- Guard st.types from localStorage with `Array.isArray`.
- Tests: chip filtering, the one-type case, stale localStorage, hostile panel values.
