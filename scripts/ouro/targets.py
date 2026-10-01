"""Targets: read from the Vitis installation, never kept in the repository.

The program asks, in order: which family, then which FPGA -- a board (which
fixes the exact part) or a bare device (then its package and speed grade).
Every answer comes from what the pinned AMD install says it has:

  - families and their devices: Vitis/data/installed.devices
  - a device's packages: Vitis/data/parts/xilinx/<family>/public/ibis/pkg/
  - boards: the AMD board store shipped with the tools (data/xhub/boards)
  - Vitis platforms: Vitis/base_platforms
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ATTR = re.compile(r'(\w+)="([^"]*)"')

# Display names for AMD's family codes, for the menu only. A code missing
# here is shown as it is; nothing depends on this table being complete.
FAMILY_NAMES = {
    "artix7": "Artix-7", "artix7l": "Artix-7 (low voltage)", "artixuplus": "Artix UltraScale+",
    "spartan7": "Spartan-7", "spartanuplus": "Spartan UltraScale+",
    "kintex7": "Kintex-7", "kintexu": "Kintex UltraScale", "kintexuplus": "Kintex UltraScale+",
    "virtex7": "Virtex-7", "virtexu": "Virtex UltraScale", "virtexuplus": "Virtex UltraScale+",
    "virtexuplusHBM": "Virtex UltraScale+ HBM", "virtexuplus58g": "Virtex UltraScale+ 58G",
    "zynq": "Zynq-7000", "zynquplus": "Zynq UltraScale+ MPSoC (incl. Kria)",
    "zynquplusRFSOC": "Zynq UltraScale+ RFSoC", "versal": "Versal",
}
PREFIX = {"a": "automotive", "q": "defense-grade", "qr": "space-grade"}


def family_name(code: str) -> str:
    """A readable name for a family code: an optional grade prefix (a, q, qr),
    a known base family, and an optional sub-family suffix (a, b, c, l, or an
    RFSoC generation like 4xdr)."""
    for prefix in ("qr", "a", "q", ""):
        if not code.startswith(prefix):
            continue
        rest = code[len(prefix):]
        m = re.fullmatch(r"(.+?)(\d?xdr|[a-fl])?", rest)
        for base in (rest, m.group(1) if m else rest):
            if base in FAMILY_NAMES:
                name = FAMILY_NAMES[base]
                extra = rest[len(base):]
                if extra:
                    name += f" ({extra})"
                if prefix:
                    name += f", {PREFIX[prefix]}"
                return name
    return code


def vitis(tools_root: Path) -> Path:
    return tools_root / "Vitis"


def families(tools_root: Path) -> list[dict]:
    """[{code, name, devices}] as Vitis lists them."""
    f = vitis(tools_root) / "data" / "installed.devices"
    data = json.loads(f.read_text())
    out = [{"code": fam["name"], "name": family_name(fam["name"]), "devices": sorted(fam["devices"])}
           for fam in data["families"]]
    return sorted(out, key=lambda x: x["name"].lower())


def family_of(device: str, tools_root: Path) -> str | None:
    for fam in families(tools_root):
        if device in fam["devices"]:
            return fam["code"]
    return None


def packages(device: str, tools_root: Path) -> list[str]:
    """A device's packages, from the package files Vitis installs."""
    parts = vitis(tools_root) / "data" / "parts" / "xilinx"
    out = set()
    for pkg in parts.glob(f"*/public/ibis/pkg/{device}_*.pkg"):
        out.add(pkg.stem[len(device) + 1:])
    return sorted(out)


def _version_key(p: Path):
    return [int(x) if x.isdigit() else x for x in re.split(r"[._]", p.name)]


def boards(tools_root: Path) -> list[dict]:
    """Every board in the AMD board store, newest version of each, with the
    part it names (none for carriers and add-on cards) and its family."""
    root = tools_root / "data" / "xhub" / "boards" / "XilinxBoardStore" / "boards"
    out = []
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
            a = dict(ATTR.findall(head.group(0))) if head else {}
            m = re.search(r'part_name="([^"]+)"', text)
            part = m.group(1) if m else None   # as the board file spells it
            out.append({
                "id": f"{a.get('vendor', vendor_dir.name)}:{a.get('name', board_dir.name)}",
                "name": a.get("display_name", board_dir.name),
                "version": versions[-1].name,
                "part": part,
                "device": part.split("-")[0].lower() if part else None,
                "file": str(xml),
                "connectors": sorted(set(re.findall(r'<component name="([^"]+)"[^>]*type="connector"', text))),
                **io_and_memory(versions[-1], text),
            })
    for b in out:
        b["family"] = family_of(b["device"], tools_root) if b["device"] else None
    return out


def io_and_memory(board_dir: Path, text: str) -> dict:
    """What a board file and its processing-system presets say the board has:
    fabric-side interfaces, PS peripherals the presets enable, and memory."""
    fabric = []
    for tag in re.findall(r"<interface [^>]*>", text):
        a = dict(ATTR.findall(tag))
        kind = a.get("type", "").split(":")[2] if a.get("type", "").count(":") >= 2 else a.get("type", "")
        if kind.startswith("fixedio"):
            continue    # the processing system's dedicated pins, not a fabric interface
        fabric.append({"name": a.get("name"), "type": kind.replace("_rtl", "")})
    ps, memory = set(), []
    for preset in board_dir.glob("*.xml"):
        if preset.name in ("board.xml", "part0_pins.xml"):
            continue
        ptext = preset.read_text(errors="replace")
        ps |= set(re.findall(r'PSU__([A-Z0-9_]+?)__PERIPHERAL__ENABLE" value="1"', ptext))
        ddr = dict(re.findall(r'PSU__DDRC__([A-Z_]+)" value="([^"]*)"', ptext))
        if ddr.get("MEMORY_TYPE"):
            entry = {"where": "processing system", "type": ddr["MEMORY_TYPE"].replace(" ", ""),
                     "bus_bits": _int(ddr.get("BUS_WIDTH")), "speed": ddr.get("SPEED_BIN")}
            dev_mbit, dram_bits = _int(ddr.get("DEVICE_CAPACITY")), _int(ddr.get("DRAM_WIDTH"))
            if dev_mbit and dram_bits and entry["bus_bits"]:
                entry["bytes"] = dev_mbit * (entry["bus_bits"] // dram_bits) * 1024 * 1024 // 8
            memory.append(entry)
    for f in fabric:
        if re.match(r"(ddr|lpddr|qdr|rldram|hbm)", f["type"] or ""):
            memory.append({"where": "fabric pins", "type": f["type"], "interface": f["name"]})
    return {"fabric_io": fabric, "ps_peripherals": sorted(ps), "memory": memory}


def _int(text):
    m = re.search(r"\d+", text or "")
    return int(m.group(0)) if m else None


def companions(board: dict, all_boards: list[dict]) -> list[dict]:
    """Boards that plug into this one through a shared connector -- a Kria
    SOM's carrier card, and the reverse."""
    if not board.get("connectors"):
        return []
    return [b for b in all_boards if b is not board and set(b.get("connectors", [])) & set(board["connectors"])
            and not b["part"]]


def describe(board: dict, all_boards: list[dict]) -> dict:
    """A board together with its companions: everything the program can offer
    for this target, read from the board store."""
    parts = [board] + companions(board, all_boards)
    memory = [m for b in parts for m in b["memory"]]
    seen, mem = set(), []
    for m in memory:
        key = (m["where"], m["type"], m.get("bytes"))
        if key not in seen:
            seen.add(key)
            mem.append(m)
    return {"boards": [b["id"] for b in parts],
            "fabric_io": [dict(f, board=b["id"]) for b in parts for f in b["fabric_io"]],
            "ps_peripherals": sorted({p for b in parts for p in b["ps_peripherals"]}),
            "memory": mem}


def platforms(tools_root: Path) -> list[dict]:
    base = vitis(tools_root) / "base_platforms"
    return [{"id": p.name, "file": str(p)} for p in sorted(base.iterdir()) if p.is_dir()] if base.exists() else []


def resolve(name: str, tools_root: Path) -> dict:
    """A target given as a board (id or short name) or as a full part string
    (device-package-speed). Returns {name, part, device, family, source}, and
    for a board its I/O and memory (see describe)."""
    all_boards = boards(tools_root)
    for b in all_boards:
        if name in (b["id"], b["id"].split(":", 1)[1]):
            if not b["part"]:
                raise LookupError(f"{b['id']} names no part -- a carrier or add-on card; pick its module")
            return {"name": b["name"], "part": b["part"], "device": b["device"], "family": b["family"],
                    "source": b["file"], **describe(b, all_boards)}
    device = name.lower().split("-")[0]
    fam = family_of(device, tools_root)
    if fam is None:
        raise LookupError(f"'{name}' is neither a board in the AMD board store nor a device Vitis has installed")
    if name.count("-") < 2:
        raise LookupError(f"{device} ({family_name(fam)}): give the full part, device-package-speed "
                          f"(packages: {', '.join(packages(device, tools_root)) or 'none listed'})")
    return {"name": name, "part": name.lower(), "device": device, "family": fam, "source": "Vitis installed devices"}
