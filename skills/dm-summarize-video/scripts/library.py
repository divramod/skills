#!/usr/bin/env python3
"""Library index + sidebar for the HTML pages: <root>/library.js lists every summarized video.

Pages are opened from file://, where a page can't list folders or fetch JSON, but it can load a
<script>. So every page loads <root>/library.js (window.DM_LIBRARY = {...}) and draws the
sidebar from it: folder tree, or sorted by download date / title / author, ascending or
descending. The index is rebuilt whenever a summary is saved, so older pages stay current.

Usage: library.py [--root DIR] [--pages]   (rebuild library.js; --pages also re-renders every page)
       library.py --open-last                (open the most recently summarized video's page)
Prints the written index path.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from _common import SkillError, library_root, log, read_json, run_main

INDEX_FILE = "library.js"


def root_of(folder: Path) -> Path | None:
    """Library root containing folder, or None when the folder lives elsewhere (no sidebar)."""
    root = library_root().resolve()
    try:
        folder.resolve().relative_to(root)
    except ValueError:
        return None
    return root


def downloaded_at(folder: Path, meta: dict) -> str:
    """When the video entered the library: prepared_at, else prepared date + transcript mtime."""
    if meta.get("prepared_at"):
        return meta["prepared_at"]
    stamp = folder / "transcript.md"
    stamp = stamp if stamp.exists() else folder / "metadata.json"
    mtime = datetime.fromtimestamp(stamp.stat().st_mtime).isoformat(timespec="seconds")
    return f"{meta['prepared']}T{mtime[11:]}" if meta.get("prepared") else mtime


def summarized_at(folder: Path, meta: dict) -> str:
    """When the summary was written: summary.created_at, else the note's mtime."""
    created = (meta.get("summary") or {}).get("created_at")
    if created:
        return created
    note = folder / ("digest.md" if meta.get("kind") == "digest" else "summary.md")
    return datetime.fromtimestamp(note.stat().st_mtime).isoformat(timespec="seconds") if note.exists() else ""


def last_summarized(root: Path) -> Path | None:
    """Page of the most recently summarized video (digests excluded), or None."""
    videos = [e for e in entries(root) if e["kind"] == "video"]
    if not videos:
        return None
    return root / max(videos, key=lambda e: e["summarized"])["page"]


def entries(root: Path) -> list[dict]:
    """One entry per folder under root that has an HTML page."""
    out = []
    for meta_path in sorted(root.rglob("metadata.json")):
        folder = meta_path.parent
        meta = read_json(meta_path)
        digest = meta.get("kind") == "digest"
        page = folder / ("digest.html" if digest else "summary.html")
        if not meta or not page.exists():
            continue
        rel = folder.relative_to(root).as_posix()
        out.append({
            "path": rel,
            "page": f"{rel}/{page.name}",
            "title": meta.get("title") or folder.name,
            "author": meta.get("channel") or meta.get("uploader") or meta.get("user") or "",
            "date": downloaded_at(folder, meta),
            "kind": "digest" if digest else "video",
            "mode": (meta.get("summary") or {}).get("mode", ""),
            "summarized": summarized_at(folder, meta),
        })
    return out


def write_index(root: Path) -> Path:
    items = entries(root)
    out = root / INDEX_FILE
    payload = json.dumps({"generated": datetime.now().isoformat(timespec="seconds"), "items": items},
                         ensure_ascii=False, indent=1)
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    tmp.write_text(f"window.DM_LIBRARY = {payload};\n", encoding="utf-8")
    os.replace(tmp, out)
    return out


# ---------------------------------------------------------------- sidebar assets

SIDEBAR_CSS = """
:root{--side:300px}
body.has-lib{display:flex;align-items:flex-start}
body.has-lib main{flex:1 1 auto;min-width:0;margin:0 auto}
#lib{position:sticky;top:0;height:100vh;flex:0 0 var(--side);width:var(--side);display:flex;flex-direction:column;border-right:1px solid var(--line);background:var(--bg);font-size:.86rem;line-height:1.35;z-index:5}
#lib .bar{display:flex;gap:2px;align-items:center;padding:10px 10px 6px}
#lib .bar button{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:1px;padding:5px 6px;border-radius:6px;color:var(--muted)}
#lib .bar button:hover{background:var(--code);color:var(--fg)}
#lib .bar button[aria-pressed=true]{background:var(--code);color:var(--accent)}
#lib .bar button:focus-visible{outline:2px solid var(--accent)}
#lib .bar svg{width:17px;height:17px}
#lib .bar .dir{font-size:.72rem;width:.8em}
#lib .bar .count{margin-left:auto;color:var(--muted);font-size:.75rem}
#lib input{margin:0 10px 8px;padding:6px 9px;border:1px solid var(--line);border-radius:7px;background:var(--card);color:var(--fg);font:inherit}
#lib nav{overflow-y:auto;padding:0 6px 24px;flex:1}
#lib ul{list-style:none;margin:0;padding:0}
#lib ul ul{padding-left:12px;border-left:1px solid var(--line);margin-left:8px}
#lib li{margin:0}
#lib a{display:block;padding:4px 8px;border-radius:6px;color:var(--fg);text-decoration:none}
#lib a:hover{background:var(--code)}
#lib a.current{background:var(--code);color:var(--accent);font-weight:600}
#lib a small{display:block;color:var(--muted);font-size:.74rem;margin-top:1px}
#lib details{margin:0;border:0;padding:0}
#lib summary{font-weight:500;padding:4px 6px;border-radius:6px;list-style:none;display:flex;gap:5px;align-items:center;color:var(--fg)}
#lib summary::-webkit-details-marker{display:none}
#lib summary::before{content:"\\25B8";font-size:.7rem;color:var(--muted);transition:transform .15s}
#lib details[open]>summary::before{transform:rotate(90deg)}
#lib summary:hover{background:var(--code)}
#lib .group{margin:10px 8px 2px;font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
#lib .empty{padding:10px;color:var(--muted)}
#lib-toggle{display:none}
@media (max-width:700px){
  body.has-lib{display:block}
  #lib{position:fixed;inset:0 auto 0 0;height:auto;transform:translateX(-100%);transition:transform .2s;box-shadow:0 0 30px rgba(0,0,0,.2)}
  body.lib-open #lib{transform:none}
  #lib-toggle{all:unset;display:block;cursor:pointer;position:fixed;top:10px;left:10px;z-index:6;padding:6px 9px;border-radius:7px;background:var(--code);color:var(--fg)}
  body.lib-open #lib-toggle{left:calc(var(--side) + 10px)}
}
"""

_ICONS = {
    "tree": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2h8.5A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z"/>',
    "date": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "title": '<text x="12" y="16.5" text-anchor="middle" font-size="12.5" font-weight="600" fill="currentColor" '
             'stroke="none" font-family="system-ui,sans-serif">Az</text>',
    "author": '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5"/>',
}
_LABELS = {"tree": "Folders", "date": "Download date", "title": "Title", "author": "Author"}


def sidebar_html() -> str:
    buttons = "".join(
        f'<button type="button" data-view="{k}" title="{_LABELS[k]}" aria-label="{_LABELS[k]}" aria-pressed="false">'
        f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round">{path}</svg><span class="dir"></span></button>'
        for k, path in _ICONS.items())
    return (f'<button type="button" id="lib-toggle" aria-label="Library">☰</button>'
            f'<aside id="lib" aria-label="Library" hidden><div class="bar">{buttons}<span class="count"></span></div>'
            f'<input type="search" placeholder="Filter…" aria-label="Filter summaries"><nav></nav></aside>')


SIDEBAR_JS = r"""
(()=>{
const L=window.DM_LIBRARY, aside=document.getElementById('lib');
if(!L||!aside)return;
const ROOT=document.body.dataset.root, SELF=document.body.dataset.self;
const nav=aside.querySelector('nav'), q=aside.querySelector('input');
const DEF={view:'tree',dir:{tree:1,date:-1,title:1,author:1}};
let st=DEF;
try{st=Object.assign({},DEF,JSON.parse(localStorage.getItem('dm-lib')||'{}'));st.dir=Object.assign({},DEF.dir,st.dir);}catch(e){}
const save=()=>{try{localStorage.setItem('dm-lib',JSON.stringify(st))}catch(e){}};
const col=new Intl.Collator(undefined,{sensitivity:'base',numeric:true});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const day=d=>(d||'').slice(0,10);
const link=(it,sub)=>`<li><a href="${esc(ROOT+'/'+it.page)}"${it.path===SELF?' class="current" aria-current="page"':''} title="${esc(it.path)}">${esc(it.title)}${sub?`<small>${esc(sub)}</small>`:''}</a></li>`;
function tree(items,d){
  const t={};
  for(const it of items){const parts=it.path.split('/');parts.pop();let n=t;for(const p of parts){n=n[p]=n[p]||{};}(n['\0']=n['\0']||[]).push(it);}
  const rec=n=>{
    const dirs=Object.keys(n).filter(k=>k!=='\0').sort((a,b)=>d*col.compare(a,b));
    const files=(n['\0']||[]).sort((a,b)=>d*col.compare(a.path.split('/').pop(),b.path.split('/').pop()));
    return '<ul>'+dirs.map(k=>{const inner=rec(n[k]);const open=SELF&&inner.includes('aria-current')||q.value?' open':'';
      return `<li><details${open}><summary>${esc(k)}</summary>${inner}</details></li>`;}).join('')+files.map(it=>link(it,it.author)).join('')+'</ul>';
  };
  return rec(t);
}
function render(){
  const f=q.value.trim().toLowerCase();
  const items=L.items.filter(it=>!f||(it.title+' '+it.author+' '+it.path).toLowerCase().includes(f));
  const d=st.dir[st.view];
  let h='';
  if(!items.length)h='<p class="empty">No summaries match.</p>';
  else if(st.view==='tree')h=tree(items,d);
  else if(st.view==='date'){
    const s=items.slice().sort((a,b)=>d*(a.date<b.date?-1:a.date>b.date?1:0));let last='';
    for(const it of s){const g=day(it.date);if(g!==last){if(last)h+='</ul>';h+=`<div class="group">${esc(g)}</div><ul>`;last=g;}h+=link(it,it.author);}
    h+='</ul>';
  }else if(st.view==='title'){
    h='<ul>'+items.slice().sort((a,b)=>d*col.compare(a.title,b.title)).map(it=>link(it,it.author)).join('')+'</ul>';
  }else{
    const s=items.slice().sort((a,b)=>d*col.compare(a.author,b.author)||col.compare(a.title,b.title));let last=null;
    for(const it of s){if(it.author!==last){if(last!==null)h+='</ul>';h+=`<div class="group">${esc(it.author||'unknown')}</div><ul>`;last=it.author;}h+=link(it,day(it.date));}
    h+='</ul>';
  }
  nav.innerHTML=h;
  aside.querySelector('.count').textContent=items.length;
  for(const b of aside.querySelectorAll('.bar button')){
    const on=b.dataset.view===st.view;b.setAttribute('aria-pressed',on);
    b.querySelector('.dir').textContent=on?(st.dir[st.view]>0?'↑':'↓'):'';
    b.title=`${b.getAttribute('aria-label')} (${st.dir[b.dataset.view]>0?'ascending':'descending'})`+(on?' – click to reverse':'');
  }
  const cur=nav.querySelector('a.current');if(cur&&!render.done){cur.scrollIntoView({block:'center'});render.done=1;}
}
aside.querySelector('.bar').addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(st.view===b.dataset.view)st.dir[st.view]*=-1;else st.view=b.dataset.view;
  save();render();
});
q.addEventListener('input',render);
document.getElementById('lib-toggle').addEventListener('click',()=>document.body.classList.toggle('lib-open'));
aside.hidden=false;document.body.classList.add('has-lib');
render();
})();
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, help="library root (default: $DM_SUMMARIZE_VIDEO_ROOT or ~/me/summaries/videos)")
    ap.add_argument("--pages", action="store_true", help="also re-render every summary.html / digest.html")
    ap.add_argument("--open-last", action="store_true",
                    help="open the most recently summarized video in the browser (via the library server)")
    args = ap.parse_args(argv)
    if args.root:
        os.environ["DM_SUMMARIZE_VIDEO_ROOT"] = str(args.root)
    root = library_root().resolve()
    if args.open_last:
        page = last_summarized(root)
        if page is None:
            raise SkillError(f"no summaries in {root} yet: pass a video URL")
        from render_html import open_page
        print(page)
        print(open_page(page))
        return 0
    if args.pages:
        from render_html import write
        for meta_path in sorted(root.rglob("metadata.json")):
            folder = meta_path.parent
            if (folder / "summary.md").exists() or (folder / "digest.md").exists():
                log(f"rendering {write(folder, index=False)}")
    print(write_index(root))
    return 0


if __name__ == "__main__":
    run_main(main)
