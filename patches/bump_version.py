#!/usr/bin/env python3
"""Set the versionCode in a binary AndroidManifest.xml.

The stock port is versionCode 404; devices that received one of the earlier
test builds carry a higher code and refuse in-place updates ("downgrade
detected"). Every pipeline build therefore stamps a versionCode above any
build that has shipped (406+).

Binary AXML, no size changes: the versionCode attribute's typed value data is
a single 32-bit word, patched in place.

Usage: bump_version.py <AndroidManifest.xml> <new-version-code>
"""
import struct
import sys


def read_strings(data: bytes, chunk_off: int) -> list[str]:
    _, _, strings_start = struct.unpack_from("<HHI", data, chunk_off + 4)
    count, _, flags, ss, _ = struct.unpack_from("<IIIII", data, chunk_off + 8)
    offsets = struct.unpack_from(f"<{count}I", data, chunk_off + 28)
    strings = []
    for o in offsets:
        p = chunk_off + ss + o
        if flags & 0x100:  # UTF-8
            n = data[p]
            p += 2 if n & 0x80 else 1
            n = data[p]
            p += 2 if n & 0x80 else 1
            strings.append(data[p:p + n].decode("utf-8"))
        else:
            n = struct.unpack_from("<H", data, p)[0]
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, p + 2)[0]
                p += 4
            else:
                p += 2
            strings.append(data[p:p + n * 2].decode("utf-16-le"))
    return strings


def bump(path: str, version_code: int) -> None:
    data = bytearray(open(path, "rb").read())
    strings = None
    off = 8
    manifest_off = None
    while off < len(data):
        ctype, _, csize = struct.unpack_from("<HHI", data, off)
        if ctype == 0x0001:
            strings = read_strings(data, off)
        elif ctype == 0x0102:  # start element
            name_idx = struct.unpack_from("<I", data, off + 20)[0]
            if strings and name_idx < len(strings) and strings[name_idx] == "manifest":
                manifest_off = off
                break
        off += csize
    if manifest_off is None:
        sys.exit("no <manifest> element found")

    a_start, a_size, a_count = struct.unpack_from("<HHH", data, manifest_off + 24)
    abase = manifest_off + 16 + a_start
    for i in range(a_count):
        a = abase + i * a_size
        name_idx = struct.unpack_from("<I", data, a + 4)[0]
        if strings[name_idx] == "versionCode":
            old = struct.unpack_from("<I", data, a + 16)[0]
            struct.pack_into("<I", data, a + 16, version_code)
            open(path, "wb").write(bytes(data))
            print(f"versionCode: {old} -> {version_code}")
            return
    sys.exit("versionCode attribute not found")


if __name__ == "__main__":
    bump(sys.argv[1], int(sys.argv[2]))
