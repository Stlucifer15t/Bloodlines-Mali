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


def build(original: str, out: str, driver: str | None, key: str, cert: str) -> None:
    work = Path(tempfile.mkdtemp(prefix="blbuild."))
    apk = work / "patched.apk"
    shutil.copyfile(original, apk)

    # strip the entries we replace or that belong to the old signature
    remove = ["classes.dex", "lib/arm64-v8a/libmain.so", DRIVER_SLOT, "META-INF/*"]
    run("zip", "-q", "-d", str(apk), *remove)

    with zipfile.ZipFile(original) as z:
        z.extract("classes.dex", work)
        z.extract("lib/arm64-v8a/libmain.so", work)

    run(sys.executable, str(ROOT / "patches/dex_always_extract.py"), str(work / "classes.dex"))
    run(sys.executable, str(ROOT / "patches/libmain_mali_driver.py"), str(work / "lib/arm64-v8a/libmain.so"))

    run("zip", "-q", str(apk), "classes.dex", cwd=work)
    run("zip", "-q", str(apk), "lib/arm64-v8a/libmain.so", cwd=work)

    if driver:
        slot = work / DRIVER_SLOT
        slot.parent.mkdir(parents=True, exist_ok=True)
        run(sys.executable, str(ROOT / "patches/repack_driver.py"), driver, str(slot))
        run("zip", "-q", str(apk), DRIVER_SLOT, cwd=work)

    run(
        sys.executable, "-c",
        "from sign_apk.cli import main; import sys; "
        f"sys.argv=['sign-apk','sign',{str(apk)!r},{out!r},'--key',{key!r},'--cert',{cert!r}']; main()",
    )
    shutil.rmtree(work, ignore_errors=True)
    print(f"done: {out}")


if __name__ == "__main__":
    args = sys.argv[1:]
    driver = None
    if "--driver" in args:
        i = args.index("--driver")
        driver = args[i + 1]
        del args[i:i + 2]
    original, out = args[0], args[1]
    key = str(ROOT / "keys/debug.pem")
    cert = str(ROOT / "keys/debug.crt")
    build(original, out, driver, key, cert)
