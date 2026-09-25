#!/usr/bin/env python3
"""Render a library folder's summary.md (or digest.md) as a self-contained summary.html.

The page holds a library sidebar (library.py), the summary, the source's header panel
(HEADER_PANELS), keyframes (when extracted) and the full content file in a collapsed section.
Video's panel is a player: the local video when downloaded, else the YouTube embed (served over
http by serve_library.py; from file:// a thumbnail that opens YouTube). Timestamp links seek
whichever player is there. Stdlib only: a small Markdown renderer covers what the templates,
content.md and frames/index.md use (headings, lists, tables, quotes, code, links, images, emphasis).

Usage: render_html.py <folder> [--open]   (save_summary.py calls this automatically;
       --open serves the library via serve_library.py and opens the page in the browser)
Prints the written file path.
"""
from __future__ import annotations

import argparse
import html
import re
import os
import webbrowser
from pathlib import Path

from _common import SkillError, contract, read_json, run_main
from library import INDEX_FILE, SIDEBAR_CSS, SIDEBAR_JS, root_of, sidebar_html, write_index

# ---------------------------------------------------------------- markdown

_TS_RE = re.compile(r"[?&#]t=(\d+)s?$")
_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)


def split_frontmatter(text: str) -> tuple[dict, str]:
    """(flat key -> value dict, rest). Values are the JSON scalars save_summary.py writes."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(0).splitlines()[1:-1]:
        key, _, val = line.partition(":")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] == '"':
            val = val[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        meta[key.strip()] = val
    return meta, text[m.end():]


_UNSAFE_URL_RE = re.compile(r"^(javascript|vbscript|data(?!:image/(png|jpe?g|gif|webp|avif)[;,])):", re.I)


def _url_attr(url: str, base: str) -> str:
    """href/src value: relative targets resolved against base; script URLs (javascript:, vbscript:, non-image
    data:) from untrusted page content become a dead "#"."""
    if _UNSAFE_URL_RE.match(re.sub(r"[\x00-\x20]+", "", url)):
        return "#"
    if base and not re.match(r"^([a-z][a-z0-9+.-]*:|/|#)", url, re.I):
        url = base + url
    return html.escape(url, quote=True)


def inline(text: str, base: str = "") -> str:
    """Inline Markdown -> HTML. Code spans are protected from the other rules."""
    slots: list[str] = []
    text = text.replace("\x00", "")  # the slot marker; a stray one in page text would never be resolved

    def keep(fragment: str) -> str:
        slots.append(fragment)
        return f"\x00{len(slots) - 1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: keep(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(r"!\[([^\]]*)\]\(((?:[^()\s]|\([^()\s]*\))+)\)", lambda m: keep(
        f'<img src="{_url_attr(m.group(2), base)}" alt="{html.escape(m.group(1), quote=True)}" loading="lazy">'), text)

    def link(m: re.Match) -> str:
        label, url = m.group(1), m.group(2)
        ts = _TS_RE.search(url)
        data = f' data-t="{ts.group(1)}"' if ts else ""
        cls = ' class="ts"' if ts else ""
        # Every link opens in a new tab so the summary stays open. Timestamp links too: with a player on the
        # page, the script seeks it instead; without one they open the video at that moment in a new tab.
        return keep(f'<a href="{_url_attr(url, base)}"{cls}{data} target="_blank" rel="noopener">{inline(label, base)}</a>')

    text = re.sub(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)", link, text)
    text = re.sub(r"(?<![\"'=])\bhttps?://[^\s<>)\]]+[^\s<>)\].,;:!?]",
                  lambda m: keep(f'<a href="{_url_attr(m.group(0), "")}" target="_blank" rel="noopener">'
                                 f'{html.escape(m.group(0))}</a>'), text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])",
                  lambda m: f"<em>{m.group(1) or m.group(2)}</em>", text)
    while re.search(r"\x00\d+\x00", text):  # slots nest: a link label holds a code span
        text = re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], text)
    return text


_LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _render_list(items: list[tuple[int, str, str]], base: str) -> str:
    """items: (indent, marker, text). Nested by indentation."""
    out: list[str] = []
    stack: list[tuple[int, str]] = []  # (indent, tag)
    for indent, marker, text in items:
        tag = "ol" if marker[0].isdigit() else "ul"
        while stack and indent < stack[-1][0]:
            out.append(f"</li></{stack.pop()[1]}>")
        if stack and indent == stack[-1][0]:
            out.append("</li>")
            if tag != stack[-1][1]:
                out.append(f"</{stack.pop()[1]}><{tag}>")
                stack.append((indent, tag))
        else:
            out.append(f"<{tag}>")
            stack.append((indent, tag))
        out.append(f"<li>{inline(text, base)}")
    while stack:
        out.append(f"</li></{stack.pop()[1]}>")
    return "".join(out)


def markdown(text: str, base: str = "") -> str:
    """Block-level Markdown -> HTML. `base` prefixes relative link/image URLs."""
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            i += 1
            continue
        if stripped.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", stripped)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2), base)}</h{level}>")
            i += 1
            continue
        if re.fullmatch(r"(-\s*){3,}|(\*\s*){3,}|(_\s*){3,}", stripped):
            out.append("<hr>")
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1]):
            head = _cells(stripped)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            th = "".join(f"<th>{inline(c, base)}</th>" for c in head)
            trs = "".join("<tr>" + "".join(f"<td>{inline(c, base)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<div class="table"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>')
            continue
        if stripped.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{markdown(chr(10).join(quote), base)}</blockquote>")
            continue
        if _LIST_RE.match(line):
            items = []
            while i < len(lines):
                lm = _LIST_RE.match(lines[i])
                if lm:
                    items.append((len(lm.group(1).expandtabs(4)), lm.group(2), lm.group(3)))
                elif lines[i].strip() and lines[i][:1].isspace() and items:  # continuation line
                    indent, marker, text = items[-1]
                    items[-1] = (indent, marker, f"{text} {lines[i].strip()}")
                else:
                    break
                i += 1
            out.append(_render_list(items, base))
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^\s*(#{1,6}\s|```|>|\|)", lines[i]) \
                and not _LIST_RE.match(lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(para), base)}</p>")
    return "\n".join(out)


# ---------------------------------------------------------------- page

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1f;--muted:#6b6b70;--line:#e4e2dc;--accent:#b4441c;--card:#fff;--code:#f1efe9}
@media (prefers-color-scheme:dark){:root{--bg:#151516;--fg:#e8e6e1;--muted:#9a9894;--line:#2d2d30;--accent:#f08a5d;--card:#1d1d1f;--code:#26262a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.65 ui-sans-serif,-apple-system,"Segoe UI",system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:40px 20px 80px}
header h1{font-size:2rem;line-height:1.2;margin:0 0 .4rem;letter-spacing:-.01em}
.meta{color:var(--muted);font-size:.92rem;margin:0}
.meta a{color:inherit}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:.8rem 0 0;padding:0;list-style:none}
.chips li{font-size:.78rem;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:1px 10px}
.player{background:var(--bg);padding:16px 0 8px;margin-top:16px}
.frame{position:relative;aspect-ratio:16/9;border-radius:10px;overflow:hidden;background:#000}
.frame iframe,.frame img{position:absolute;inset:0;width:100%;height:100%;border:0;object-fit:cover}
.frame .play{position:absolute;inset:0;display:grid;place-items:center;color:#fff;font-size:1rem;text-decoration:none;background:linear-gradient(transparent 55%,rgba(0,0,0,.55))}
.frame .play span{display:grid;place-items:center;width:68px;height:48px;border-radius:14px;background:rgba(0,0,0,.72);font-size:1.4rem}
.frame .play:hover span{background:#e62117}
.dl{display:flex;align-items:center;gap:10px;margin-top:8px;font-size:.85rem;color:var(--muted)}
.dl button{font:inherit;cursor:pointer;padding:5px 12px;border-radius:7px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
.dl button:hover:not(:disabled){border-color:var(--accent);color:var(--accent)}
.dl button:disabled{cursor:default;opacity:.6}
.dl progress{width:140px;accent-color:var(--accent)}
.player.playing{position:sticky;top:0;z-index:2}
video{width:100%;max-height:60vh;border-radius:10px;background:#000;display:block;transition:max-height .2s}
.player.playing video{max-height:32vh}
.player p{margin:.3rem 0 0;font-size:.8rem;color:var(--muted)}
article h2{font-size:1.3rem;margin:2.2rem 0 .6rem;padding-bottom:.3rem;border-bottom:1px solid var(--line)}
article h3{font-size:1.08rem;margin:1.6rem 0 .4rem}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px}
a.ts{font-variant-numeric:tabular-nums;font-size:.86em;text-decoration:none;background:var(--code);border-radius:5px;padding:0 5px;white-space:nowrap}
a.ts:hover{text-decoration:underline}
/* date labels written by check_links.py right after a link: [Title](url) *(published 2025-06-03)* */
article a:not(.ts)+em{font-style:normal;font-size:.8em;color:var(--muted);white-space:normal}
li{margin:.25rem 0}
blockquote{margin:1rem 0;padding:.2rem 1rem;border-left:3px solid var(--accent);color:var(--muted)}
code{background:var(--code);border-radius:4px;padding:1px 4px;font-size:.88em}
pre{background:var(--code);padding:12px;border-radius:8px;overflow-x:auto}
pre code{background:none;padding:0}
.table{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.93rem}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
td img{max-width:220px;border-radius:6px}
img{max-width:100%}
details{margin-top:2.5rem;border-top:1px solid var(--line);padding-top:1rem}
summary{cursor:pointer;font-weight:600}
details.content article{font-size:.95rem}
footer{margin-top:3rem;color:var(--muted);font-size:.8rem}
"""

JS = """
const v=document.querySelector('video');
if(v){const p=v.parentElement;v.addEventListener('play',()=>p.classList.add('playing'));v.addEventListener('pause',()=>p.classList.remove('playing'));}
// YouTube embeds need a Referer, which file:// pages don't send: embed only when served over http.
const yt=document.querySelector('.frame[data-yt]');let ytf=null;
if(yt&&location.protocol.startsWith('http')){
  ytf=document.createElement('iframe');
  ytf.src=`https://www.youtube-nocookie.com/embed/${yt.dataset.yt}?enablejsapi=1&rel=0&playsinline=1&origin=${encodeURIComponent(location.origin)}`;
  ytf.allow='autoplay; encrypted-media; picture-in-picture; fullscreen';ytf.allowFullscreen=true;
  ytf.referrerPolicy='strict-origin-when-cross-origin';ytf.title='YouTube player';
  ytf.addEventListener('load',()=>ytf.contentWindow.postMessage('{"event":"listening"}','*'));
  yt.replaceChildren(ytf);document.querySelector('.player .hint')?.remove();
}
// Download the video into this folder via the library server, then reload to play it locally.
const dl=document.querySelector('.dl:not(.rm)'),rm=document.querySelector('.dl.rm'),self=document.body.dataset.self;
const post=(p,b)=>fetch(p,{method:'POST',headers:{'X-DM-Summarize':'1','Content-Type':'application/json'},body:JSON.stringify(b)}).then(r=>r.json());
if(rm&&self&&location.protocol.startsWith('http')){
  rm.hidden=false;
  const btn=rm.querySelector('button'),out=rm.querySelector('.dl-status');
  btn.addEventListener('click',()=>{
    if(!confirm('Delete the downloaded video? The summary stays; you can download the video again from this page.'))return;
    btn.disabled=true;
    post('/api/delete-video',{path:self}).then(s=>{if(s.error){out.textContent=s.error;btn.disabled=false;}else location.reload();})
      .catch(e=>{btn.disabled=false;out.textContent='Server not reachable: '+e;});
  });
}
if(dl&&self&&location.protocol.startsWith('http')){
  const btn=dl.querySelector('button'),out=dl.querySelector('.dl-status');
  const api=(m,p,b)=>fetch(p,{method:m,headers:{'X-DM-Summarize':'1','Content-Type':'application/json'},body:b&&JSON.stringify(b)}).then(r=>r.json());
  let timer=null;
  const show=s=>{
    if(s.status==='done'){out.textContent='Downloaded, loading the local video…';clearInterval(timer);setTimeout(()=>location.reload(),600);return;}
    if(s.status==='running'){
      btn.disabled=true;btn.textContent='Downloading…';
      const pct=s.progress!=null?`${s.stream>1?'audio':'video'} ${s.progress.toFixed(0)}%`:'starting';
      out.innerHTML=`<progress max="100" value="${s.progress||0}"></progress> ${pct}`;
      if(!timer)timer=setInterval(()=>api('GET','/api/status?path='+encodeURIComponent(self)).then(show).catch(()=>{}),1500);
      return;
    }
    clearInterval(timer);timer=null;btn.disabled=false;
    if(s.status==='failed'){btn.textContent='⬇ Retry download';out.textContent='Failed: '+(s.error||'').split('\\n')[0];}
  };
  btn.addEventListener('click',()=>{btn.disabled=true;api('POST','/api/download',{path:self}).then(show).catch(e=>{btn.disabled=false;out.textContent='Server not reachable: '+e;});});
  api('GET','/api/status?path='+encodeURIComponent(self)).then(s=>{dl.hidden=false;show(s);}).catch(()=>{});
}
const ytc=(func,args=[])=>ytf.contentWindow.postMessage(JSON.stringify({event:'command',func,args}),'*');
document.addEventListener('click',e=>{
  const a=e.target.closest('a.ts');
  if(!a||e.metaKey||e.ctrlKey||e.shiftKey)return;
  const t=+a.dataset.t;
  if(v&&!v.error){e.preventDefault();v.currentTime=t;v.play();v.scrollIntoView({block:'nearest',behavior:'smooth'});}
  else if(ytf){e.preventDefault();ytc('seekTo',[t,true]);ytc('playVideo');ytf.scrollIntoView({block:'nearest',behavior:'smooth'});}
});
"""


def fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def player_html(folder: Path, meta: dict, url: str | None) -> str:
    """Local video > YouTube embed (thumbnail from file://) > box linking to the source; plus a download button."""
    video = meta.get("video_file")
    if video and (folder / video).exists() and not (folder / ".video-download.json").exists():
        size = (folder / video).stat().st_size
        # Delete button: needs the library server, so the script unhides it over http.
        rm = (f'<div class="dl rm" hidden><button type="button">🗑 Delete downloaded video</button>'
              f'<span class="dl-status" role="status">{html.escape(video)}, {fmt_size(size)}</span></div>')
        return (f'<div class="player"><video controls preload="metadata" src="{html.escape(video, quote=True)}"></video>'
                f"<p>Timestamps play here; Cmd/Ctrl-click opens them on the site.</p>{rm}</div>")
    youtube = meta.get("platform") == "youtube" and meta.get("id")
    thumb = f"https://i.ytimg.com/vi/{meta['id']}/hqdefault.jpg" if youtube else meta.get("thumbnail")
    if not url:
        return ""
    img = f'<img src="{html.escape(thumb, quote=True)}" alt="" loading="lazy">' if thumb else ""
    data = f' data-yt="{html.escape(meta["id"], quote=True)}"' if youtube else ""
    hint = ("<p class=\"hint\">From file:// the video opens on the site. For inline playback and the download "
            "button open the page via <code>serve_library.py --ensure</code> (<code>--open</code> does this).</p>")
    # Download button: needs the library server (serve_library.py /api), so the script unhides it over http.
    dl = ('<div class="dl" hidden><button type="button">⬇ Download video</button>'
          '<span class="dl-status" role="status">Best quality, saved in this summary’s folder.</span></div>')
    return (f'<div class="player"><div class="frame"{data}>{img}<a class="play" href="{html.escape(url, quote=True)}" '
            f'target="_blank" rel="noopener" aria-label="Play video"><span>▶</span></a></div>'
            f'<p>Timestamps play here; Cmd/Ctrl-click opens them on the site.</p>{hint}{dl}</div>')


# Per-source panel under the page header: fn(folder, metadata, url) -> html. Sources without one get none.
HEADER_PANELS = {"video": player_html}
# Label of the collapsed content-file section.
CONTENT_LABELS = {"video": "Transcript", "web": "Article", "github": "Repository", "x": "Posts",
                  "hn": "Article and discussion", "file": "Document"}


def build(folder: Path) -> str:
    meta = read_json(folder / "metadata.json")
    note = folder / ("digest.md" if meta.get("kind") == "digest" else "summary.md")
    if not note.exists():
        raise SkillError(f"{note} missing: save the summary first")
    front, body = split_frontmatter(note.read_text(encoding="utf-8"))
    title = front.get("title") or meta.get("title") or "Untitled"
    # save_summary.py writes "# title\n\ninfo line\n\n" before the body; the page renders its own header.
    c = contract(meta)
    url = front.get("url") or c["url"]
    # author/site: notes saved before the source contract have channel/platform
    info = [x for x in (front.get("author") or front.get("channel"), front.get("duration"), front.get("published")) if x]
    header_info = " · ".join(info + ([url] if url else []))
    body = re.sub(r"\A\s*# [^\n]*\n+", "", body, count=1)
    if header_info and body.startswith(header_info + "\n"):
        body = body[len(header_info) + 1:]

    meta_line = " · ".join(html.escape(x) for x in info)
    if url:
        meta_line += f' · <a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{html.escape(front.get("site") or front.get("platform") or "source")}</a>'
    chips = [front.get(k) and f"{k.replace('_', ' ')}: {front[k]}" for k in ("mode", "lang", "agent", "model", "created")]
    chips_html = "".join(f"<li>{html.escape(c)}</li>" for c in chips if c)

    panel = HEADER_PANELS.get(c["source"])
    panel_html = panel(folder, meta, url) if panel else ""

    extras = []
    frames = folder / "frames" / "index.md"
    if frames.exists():
        ftext = re.sub(r"\A# [^\n]*\n", "", frames.read_text(encoding="utf-8"))
        extras.append(f'<details><summary>Keyframes</summary><article>{markdown(ftext, "frames/")}</article></details>')
    content = folder / c["content_file"] if c["content_file"] else None
    if content and content.exists():
        ctext = re.sub(r"\A# [^\n]*\n", "", content.read_text(encoding="utf-8"))
        label = CONTENT_LABELS.get(c["source"], "Content")
        extras.append(f'<details class="content"><summary>{label}</summary><article>{markdown(ctext)}</article></details>')

    root = root_of(folder)
    sidebar = sidebar_js = body_attrs = ""
    if root is not None:
        rel_root = os.path.relpath(root, folder.resolve()).replace(os.sep, "/")
        self_path = folder.resolve().relative_to(root).as_posix()
        body_attrs = f' data-root="{html.escape(rel_root, quote=True)}" data-self="{html.escape(self_path, quote=True)}"'
        sidebar = sidebar_html()
        sidebar_js = f'<script src="{html.escape(rel_root, quote=True)}/{INDEX_FILE}"></script><script>{SIDEBAR_JS}</script>'

    return f"""<!doctype html>
<html lang="{html.escape(front.get('lang') or 'en', quote=True)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>{html.escape(title)}</title>
<style>{CSS}{SIDEBAR_CSS if sidebar else ""}</style>
</head>
<body{body_attrs}>
{sidebar}
<main>
<header>
<h1>{html.escape(title)}</h1>
<p class="meta">{meta_line}</p>
<ul class="chips">{chips_html}</ul>
</header>
{panel_html}
<article>
{markdown(body)}
</article>
{"".join(extras)}
<footer>{html.escape(note.name)} · {html.escape(str(folder))}</footer>
</main>
<script>{JS}</script>
{sidebar_js}
</body>
</html>
"""


def write(folder: Path, index: bool = True) -> Path:
    """Write the page; `index` also rebuilds <root>/library.js so every sidebar lists it."""
    meta = read_json(folder / "metadata.json")
    out = folder / ("digest.html" if meta.get("kind") == "digest" else "summary.html")
    out.write_text(build(folder), encoding="utf-8")
    root = root_of(folder)
    if index and root is not None:
        write_index(root)
    return out


def open_page(page: Path) -> str:
    """Open the page in the browser via the library server (file:// outside the library)."""
    from serve_library import page_url
    url = page_url(page)
    webbrowser.open(url)
    return url


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--open", action="store_true", help="open the page in the default browser")
    args = ap.parse_args(argv)
    out = write(args.folder)
    print(out)
    if args.open:
        print(open_page(out))
    return 0


if __name__ == "__main__":
    run_main(main)
