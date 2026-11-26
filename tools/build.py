#!/usr/bin/env python3
"""Build a patched Bloodlines APK from the original.

Steps (all verified against v0.4.2, package com.vtmb.lift):

1. copy the original APK
2. patch classes.dex  - re-extract the bundled driver on every launch
3. patch libmain.so   - Mali driver routing (imported drivers work on Mali)
4. optionally swap the bundled driver in assets/drivers/turnip_classic.zip
   (the slot the engine auto-picks on non-Adreno GPUs)
5. strip the old signature and re-sign (v2+v3) with the repo's debug key

The same signing key must be used for every build so updates install in place
without uninstalling (which would wipe the app's game import).

Usage:
  python3 tools/build.py <original.apk> <out.apk> [--driver <slot-zip>]

Requirements: python3 (stdlib only) and the `sign-apk` package
  pip install git+https://github.com/adityatelange/sign-apk-py
"""
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRIVER_SLOT = "assets/drivers/turnip_classic.zip"


def run(*cmd: str, cwd: str | None = None) -> None:
    print("+", " ".join(cmd), f"(cwd={cwd})" if cwd else "")
    subprocess.run(cmd, check=True, cwd=cwd)


def build(original: str, out: str, driver: str | None, key: str, cert: str,
          mali_routing: bool = False, version_code: int = 407) -> None:
    work = Path(tempfile.mkdtemp(prefix="blbuild."))
    apk = work / "patched.apk"
    shutil.copyfile(original, apk)

    # strip the entries we replace or that belong to the old signature
    remove = ["classes.dex", "lib/arm64-v8a/libmain.so", "AndroidManifest.xml", DRIVER_SLOT, "META-INF/*"]
    run("zip", "-q", "-d", str(apk), *remove)

    with zipfile.ZipFile(original) as z:
        z.extract("classes.dex", work)
        z.extract("lib/arm64-v8a/libmain.so", work)
        z.extract("AndroidManifest.xml", work)

    run(sys.executable, str(ROOT / "patches/dex_always_extract.py"), str(work / "classes.dex"))
    if mali_routing:
        # Only for builds that also ship a working Mali driver in a slot.
        # With the stock Adreno-only Turnip zips this makes things WORSE: the
        # engine would pick the useless Turnip driver and crash, instead of
        # the stable system-driver + DXVK path.
        run(sys.executable, str(ROOT / "patches/libmain_mali_driver.py"), str(work / "lib/arm64-v8a/libmain.so"))
    run(sys.executable, str(ROOT / "patches/bump_version.py"), str(work / "AndroidManifest.xml"), str(version_code))

    run("zip", "-q", str(apk), "classes.dex", cwd=work)
    run("zip", "-q", str(apk), "lib/arm64-v8a/libmain.so", cwd=work)
    run("zip", "-q", str(apk), "AndroidManifest.xml", cwd=work)

    if driver:
        slot = work / DRIVER_SLOT
        slot.parent.mkdir(parents=True, exist_ok=True)
        run(sys.executable, str(ROOT / "patches/repack_driver.py"), driver, str(slot))
        run("zip", "-q", str(apk), DRIVER_SLOT, cwd=work)

    run(sys.executable, str(ROOT / "tools/sign.py"), "sign", str(apk), out, "--key", key, "--cert", cert)
    shutil.rmtree(work, ignore_errors=True)
    print(f"done: {out}")


if __name__ == "__main__":
    args = sys.argv[1:]
    driver = None
    mali_routing = False
    version_code = 407
    if "--driver" in args:
        i = args.index("--driver")
        driver = args[i + 1]
        del args[i:i + 2]
    if "--mali-routing" in args:
        args.remove("--mali-routing")
        mali_routing = True
    if "--version-code" in args:
        i = args.index("--version-code")
        version_code = int(args[i + 1])
        del args[i:i + 2]
    original, out = args[0], args[1]
    key = str(ROOT / "keys/debug.pem")
    cert = str(ROOT / "keys/debug.crt")
    build(original, out, driver, key, cert, mali_routing, version_code)
