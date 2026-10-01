"""Just enough ELF64 to find a test's `tohost` symbol."""
from __future__ import annotations

import struct
from pathlib import Path


def symbols(path: Path) -> dict:
    """{name: value} from a little-endian ELF64's symbol tables. Raises on a
    malformed file rather than returning a partial table."""
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise ValueError(f"{path}: not a little-endian ELF64")
    shoff = struct.unpack_from("<Q", data, 0x28)[0]
    shentsize, shnum = struct.unpack_from("<HH", data, 0x3A)
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize) for i in range(shnum)]
    out = {}
    for sec in sections:
        stype, off, size, link, entsize = sec[1], sec[4], sec[5], sec[6], sec[9]
        if stype not in (2, 11) or entsize == 0:   # SHT_SYMTAB, SHT_DYNSYM
            continue
        strtab = sections[link]
        str_off = strtab[4]
        for i in range(size // entsize):
            name_off, _info, _other, _shndx, value, _size = struct.unpack_from("<IBBHQQ", data, off + i * entsize)
            end = data.index(b"\0", str_off + name_off)
            name = data[str_off + name_off:end].decode("ascii", "replace")
            if name:
                out[name] = value
    return out
