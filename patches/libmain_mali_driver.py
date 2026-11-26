#!/usr/bin/env python3
"""Patch libmain.so so the engine's driver-import feature works on Mali GPUs.

The engine's driver-choice code assumes custom Vulkan drivers are Adreno-only.
For a non-Adreno GPU (the `not Adreno` flag in its GPU struct) it forces
driver choice 0 (system driver), so an imported driver in slot 1 is never
loaded on Mali.

The auto-choice path computes the choice in w20 and ends with:

    19343cc: 1a9f1114  csel w20, w8, wzr, ne   ; w8 = 2, ne is false -> w20 = 0

This patch replaces that instruction with:

    19343cc: 120006b4  and  w20, w21, #1       ; w21 = "slot-1 driver unpacked"

so a non-Adreno GPU picks the custom driver when one is unpacked, exactly like
the unknown-GPU path already does. Adreno GPUs keep their original logic (they
take a different branch).

Verified on v0.4.2 (libmain.so, 105722560 bytes): with this patch the engine
logs `driver choice 1` on a Mali-G52 MC2 and loads the driver from
`files/turnip_unpacked/` through adrenotools.
"""
import struct
import sys

OFFSET = 0x19343CC - 0x1000  # .text vaddr -> file offset
OLD = 0x1A9F1114  # csel w20, w8, wzr, ne
NEW = 0x120006B4  # and  w20, w21, #1


def patch(path: str) -> None:
    data = bytearray(open(path, "rb").read())
    current = struct.unpack_from("<I", data, OFFSET)[0]
    if current == NEW:
        print("libmain.so: already patched")
        return
    if current != OLD:
        sys.exit(f"libmain.so: unexpected instruction {current:#010x} at {OFFSET:#x} - wrong engine version?")
    struct.pack_into("<I", data, OFFSET, NEW)
    open(path, "wb").write(bytes(data))
    print("libmain.so: Mali driver routing patched")


if __name__ == "__main__":
    patch(sys.argv[1])
