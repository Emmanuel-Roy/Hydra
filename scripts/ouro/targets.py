"""Targets: the boards and platforms Ouroboros can build for.

Two sources, both read-only:
  - FPGAs/<name>/target.toml -- the targets saved in this repository;
  - the library that comes with the pinned AMD tools -- every board in
    Vivado's board store, and every Vitis platform.
A target saved in FPGAs/ only names entries in that library; the part and
everything else are read from the library's own files, never written here.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ATTR = re.compile(r'(\w+)="([^"]*)"')


def _version_key(p: Path):
    return [int(x) if x.isdigit() else x for x in re.split(r"[._]", p.name)]


def _attrs(tag: str) -> dict:
    return dict(ATTR.findall(tag))


def board_store(tools_root: Path) -> Path:
    return tools_root / "data" / "xhub" / "boards" / "XilinxBoardStore" / "boards"


def library_boards(tools_root: Path) -> list[dict]:
    """Every board in the board store, newest version of each: its id
    (vendor:name), display name, part (when the board file names one) and the
    board file it came from."""
    out = []
    root = board_store(tools_root)
    if not root.exists():
        return out
    for vendor_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for board_dir in sorted(p for p in vendor_dir.iterdir() if p.is_dir()):
            versions = sorted((v for v in board_dir.iterdir() if (v / "board.xml").exists()), key=_version_key)
            if not versions:
                continue
            xml = versions[-1] / "board.xml"
            text = xml.read_text(errors="replace")
            head = re.search(r"<board\b[^>]*>", text)
            a = _attrs(head.group(0)) if head else {}
            part = re.search(r'part_name="([^"]+)"', text)
            out.append({
                "id": f"{a.get('vendor', vendor_dir.name)}:{a.get('name', board_dir.name)}",
                "name": a.get("display_name", board_dir.name),
                "version": versions[-1].name,
                "part": part.group(1) if part else None,
                "file": str(xml),
            })
    return out


def library_platforms(tools_root: Path) -> list[dict]:
    """Every Vitis platform installed with the tools (.xpfm)."""
    out = []
    for base in (tools_root / "Vitis" / "base_platforms", tools_root / "Vitis" / "platforms"):
        if base.exists():
            for x in sorted(base.rglob("*.xpfm")):
                out.append({"id": x.stem, "name": x.stem, "file": str(x)})
    return out


def saved(repo_root: Path) -> dict[str, dict]:
    out = {}
    for t in sorted((repo_root / "FPGAs").glob("*/target.toml")):
        out[t.parent.name] = tomllib.loads(t.read_text())
    return out


def resolve(name: str, repo_root: Path, tools_root: Path) -> dict:
    """A target by its FPGAs/ folder name, or by a board-store id or name from
    the library. Returns {name, part, boards, source}; raises if unknown or if
    no part can be read from the library."""
    boards = {b["id"]: b for b in library_boards(tools_root)}
    by_name = {b["id"].split(":", 1)[1]: b for b in boards.values()}
    mine = saved(repo_root)
    if name in mine:
        ids = mine[name].get("board_store", [])
        found = [boards.get(i) or by_name.get(i.split(":", 1)[-1]) for i in ids]
        missing = [i for i, b in zip(ids, found) if b is None]
        if missing:
            raise LookupError(f"FPGAs/{name}: not in the installed board store: {', '.join(missing)}")
        parts = {b["part"] for b in found if b["part"]}
        if len(parts) != 1:
            raise LookupError(f"FPGAs/{name}: its boards name {len(parts)} parts ({', '.join(sorted(parts)) or 'none'})")
        return {"name": mine[name].get("name", name), "part": parts.pop(), "boards": ids, "source": f"FPGAs/{name}"}
    b = boards.get(name) or by_name.get(name)
    if not b:
        raise LookupError(f"no target '{name}' in FPGAs/ or the installed board store")
    if not b["part"]:
        raise LookupError(f"{b['id']} names no part (a carrier card? pick its module instead)")
    return {"name": b["name"], "part": b["part"], "boards": [b["id"]], "source": b["file"]}


def save(name: str, board_ids: list[str], display: str, repo_root: Path) -> Path:
    """Save a library board as a target in FPGAs/ -- a pointer, nothing more."""
    d = repo_root / "FPGAs" / name
    d.mkdir(parents=True, exist_ok=True)
    f = d / "target.toml"
    ids = ", ".join(f'"{i}"' for i in board_ids)
    f.write_text(f'# Saved from the installed board store. Only names the platform\n'
                 f'# specification; everything else is read from it.\n\n'
                 f'name = "{display}"\nboard_store = [{ids}]\n')
    return f
