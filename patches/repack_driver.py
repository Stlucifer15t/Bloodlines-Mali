#!/usr/bin/env python3
"""Repack a Mesa PanVK (or any adrenotools-format) driver zip into an engine slot.

The engine loads custom Vulkan drivers from its three slot folders:

    files/turnip_unpacked/   (slot 1, from assets/drivers/turnip_classic.zip)
    files/turnip_gen8/       (slot 2, from assets/drivers/turnip_gen8.zip)
    files/turnip_26/         (slot 3, from assets/drivers/turnip_26.zip)

Each slot zip must contain `libvulkan_freedreno.so` (the name the engine and
the Java extractor expect) plus a `meta.json`. Driver packages built for
adrenotools-style loaders (Mesa PanVK for Mali, Turnip for Adreno) ship the
library as `libvulkan_panfrost.so` / `libvulkan_freedreno.so` plus meta.json.

This script takes such a package and produces a slot zip: the library is
renamed to `libvulkan_freedreno.so` and meta.json's `libraryName` is updated
to match. Extra files in the package are carried over.

Usage: repack_driver.py <driver-package.zip> <out-slot.zip>
"""
import json
import sys
import zipfile

LIBRARY_NAMES = ("libvulkan_panfrost.so", "libvulkan_freedreno.so")
SLOT_LIBRARY = "libvulkan_freedreno.so"


def repack(package_path: str, out_path: str) -> None:
    src = zipfile.ZipFile(package_path)
    names = src.namelist()
    library = next((n for n in names if n.split("/")[-1] in LIBRARY_NAMES), None)
    if library is None:
        sys.exit(f"no Vulkan driver library found in {package_path} (looked for {LIBRARY_NAMES})")

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name in names:
            if name.endswith("/"):
                continue
            data = src.read(name)
            base = name.split("/")[-1]
            if base == library.split("/")[-1]:
                base = SLOT_LIBRARY
            elif base == "meta.json":
                meta = json.loads(data)
                meta["libraryName"] = SLOT_LIBRARY
                data = json.dumps(meta, indent=2).encode()
            out.writestr(base, data)
    print(f"{out_path}: {library} -> {SLOT_LIBRARY}")


if __name__ == "__main__":
    repack(sys.argv[1], sys.argv[2])
