#!/usr/bin/env python3
"""Patch classes.dex so the driver zips are re-extracted on every launch.

FearActivity.onCreate calls unzipIfMissing(asset, targetDir) for the three
bundled driver zips. The "if missing" check is an early return:

    if (new File(dir, "libvulkan_freedreno.so").exists()) return;

Without a patch, a driver extracted by an older build of the app is kept
forever - installing an APK with a different bundled driver has no effect.

The patch turns the early return into a jump to the extraction code, so every
launch re-extracts the bundled driver over whatever was there:

    instruction 7 (return-void, 0x0e00) -> goto +1 (0x2801)

The dex checksum (Adler-32) and SHA-1 signature are recomputed afterwards,
which the runtime requires.

Verified on v0.4.2: classes.dex, code item of
Lcom/fear/lift/FearActivity;.unzipIfMissing at file offset 0x2e638,
instruction 7 at 0x2e666.
"""
import hashlib
import struct
import sys
import zlib

OFFSET = 0x2E666
OLD = b"\x0e\x00"  # return-void
NEW = b"\x28\x01"  # goto +1


def patch(path: str) -> None:
    data = bytearray(open(path, "rb").read())
    if bytes(data[OFFSET:OFFSET + 2]) == NEW:
        print("classes.dex: already patched")
        return
    if bytes(data[OFFSET:OFFSET + 2]) != OLD:
        sys.exit(f"classes.dex: unexpected bytes {data[OFFSET:OFFSET+2].hex()} at {OFFSET:#x} - wrong version?")
    data[OFFSET:OFFSET + 2] = NEW
    # dex file header: checksum (Adler-32) at 8, SHA-1 at 12 (over bytes 32..)
    data[12:32] = hashlib.sha1(bytes(data[32:])).digest()
    struct.pack_into("<I", data, 8, zlib.adler32(bytes(data[12:])) & 0xFFFFFFFF)
    open(path, "wb").write(bytes(data))
    print("classes.dex: always-re-extract patched, checksums fixed")


if __name__ == "__main__":
    patch(sys.argv[1])
