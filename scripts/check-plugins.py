#!/usr/bin/env python3
"""Check that the plugin manifests agree with skills/ and with each other.

- every skills/<name>/SKILL.md is listed in .claude-plugin/plugin.json `skills`, and vice versa
- each SKILL.md frontmatter `name` equals its folder name, and has a `description`
- .claude-plugin/plugin.json and .codex-plugin/plugin.json share name + version
- the plugin name matches in both marketplaces
- a skill whose scripts call external tools ships executable scripts/check-prerequisites.sh
  and scripts/install-prerequisites.sh (see CLAUDE.md, "Skill script rules")

Run: python3 scripts/check-plugins.py   (exit 1 on any problem)
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREREQ_SCRIPTS = ("check-prerequisites.sh", "install-prerequisites.sh")
# A script that contains one of these calls external command-line tools.
TOOL_MARKERS = ("subprocess", "shutil.which", "command -v", "os.system(")


def load(rel):
    return json.loads((ROOT / rel).read_text())


def main() -> int:
    errors = []
    claude = load(".claude-plugin/plugin.json")
    codex = load(".codex-plugin/plugin.json")
    claude_mkt = load(".claude-plugin/marketplace.json")
    codex_mkt = load(".agents/plugins/marketplace.json")

    on_disk = {f"./skills/{p.parent.name}" for p in (ROOT / "skills").glob("*/SKILL.md")}
    listed = set(claude.get("skills", []))
    for s in sorted(on_disk - listed):
        errors.append(f"{s} is missing from .claude-plugin/plugin.json skills")
    for s in sorted(listed - on_disk):
        errors.append(f"{s} is listed in .claude-plugin/plugin.json but has no SKILL.md")

    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        m = re.match(r"^---\n(.*?)\n---\n", skill_md.read_text(), re.S)
        front = m.group(1) if m else ""
        name = re.search(r"^name:\s*(.+)$", front, re.M)
        if not name or name.group(1).strip() != skill_md.parent.name:
            errors.append(f"{skill_md.relative_to(ROOT)}: frontmatter name must be '{skill_md.parent.name}'")
        if not re.search(r"^description:\s*\S", front, re.M):
            errors.append(f"{skill_md.relative_to(ROOT)}: frontmatter description is missing")

    for skill in sorted(p.parent for p in (ROOT / "skills").glob("*/SKILL.md")):
        scripts = skill / "scripts"
        if not scripts.is_dir():
            continue
        uses_tools = any(
            any(marker in f.read_text(errors="ignore") for marker in TOOL_MARKERS)
            for f in scripts.iterdir()
            if f.is_file() and f.suffix in (".py", ".sh") and f.name not in PREREQ_SCRIPTS
        )
        if uses_tools:
            for name in PREREQ_SCRIPTS:
                f = scripts / name
                if not f.is_file():
                    errors.append(f"{f.relative_to(ROOT)} missing (scripts call external tools)")
                elif not os.access(f, os.X_OK):
                    errors.append(f"{f.relative_to(ROOT)} is not executable")

    for key in ("name", "version"):
        if claude.get(key) != codex.get(key):
            errors.append(f"plugin {key} differs: claude={claude.get(key)} codex={codex.get(key)}")
    if codex.get("skills") != "./skills/":
        errors.append(".codex-plugin/plugin.json skills must be './skills/'")
    for label, mkt in (("claude", claude_mkt), ("codex", codex_mkt)):
        names = [p.get("name") for p in mkt.get("plugins", [])]
        if claude.get("name") not in names:
            errors.append(f"{label} marketplace does not list plugin '{claude.get('name')}'")

    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if not errors:
        print(f"ok: {len(on_disk)} skill(s), plugin {claude['name']} v{claude['version']}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
