# Bloodlines Mali

Patches and build pipeline for the **Vampire: The Masquerade – Bloodlines**
Android port (v0.4.2, package `com.vtmb.lift`), focused on making it run
properly on **Mali GPUs** (MediaTek / Exynos phones).

This is not a launcher and not a fork of the port's app. It takes the original
APK, applies small binary patches, and re-signs it — so the port's own UI,
settings and behaviour stay exactly as they are.

## What was wrong

The port runs the game through DXVK (D3D9 → Vulkan) when a custom Vulkan
driver is available, and falls back to its own slow OpenGL ES translator
otherwise. Two problems on a Mali phone:

1. **All bundled drivers are Adreno-only.** The APK ships three Turnip
   variants (`assets/drivers/turnip_*.zip`); Turnip does not initialise on
   Mali, so the game silently falls back to the slow GLES renderer.
2. **The engine hard-blocks custom drivers on non-Adreno GPUs.** Its
   driver-choice code forces choice 0 (system driver) whenever the GPU is not
   an Adreno, so even a correctly imported Mali driver (e.g. Mesa PanVK) is
   never loaded.

## The patches

| Patch | File | What it does |
| --- | --- | --- |
| Mali driver routing | `patches/libmain_mali_driver.py` | One instruction in `libmain.so`: the non-Adreno path now picks the custom driver when one is unpacked, instead of forcing the system driver. |
| Always re-extract driver | `patches/dex_always_extract.py` | One instruction in `classes.dex`: the bundled driver zip is re-extracted on every launch, so switching driver builds actually takes effect (previously the first extraction was kept forever). |
| Driver repack | `patches/repack_driver.py` | Converts any adrenotools-format driver package (Mesa PanVK, Turnip, …) into an engine slot zip. |

## Build

```bash
pip install git+https://github.com/adityatelange/sign-apk-py
python3 tools/build.py base/Bloodlines-v0.4.2.apk out.apk
# with a different bundled driver (e.g. Mesa PanVK for Mali):
python3 tools/build.py base/Bloodlines-v0.4.2.apk out.apk --driver panvk.zip
```

CI builds the patched APK on every push; the APK is in the run's artifacts.

## Install

1. **Uninstall** the stock port app first (different signature), or install
   over a previous patched build signed with the same key.
2. Install the patched APK. The game folder (`/sdcard/Download/VTMB-apkvision-English`
   or wherever the port's setup put it) is untouched.

## Tuning that lives in the game folder

The engine reads its live configuration from the game folder (a folder import
is used in place, not copied):

* `overlay/port_settings.txt` — `render_h` (render height, 0 = native),
  `fps_limit`, `ui.gfxApi` (`0.0` = Vulkan/DXVK, `1.0` = OpenGL ES renderer)
* `overlay/port_env.txt` — the engine's `FEAR_*` performance flags
  (`FEAR_MT_D3D`, `FEAR_NOVSYNC`, `FEAR_CPUPIN`, `FEAR_FIXED_FPS`, …)
* `overlay/iq_high.txt` — image-quality switch (probed for existence)
* `Vampire/cfg/config.cfg` — the game's own console config;
  `particles_enable_precipitation 0` is the known fix for the outdoor
  frame-rate collapse (the particle system is slow and the Santa Monica hub rains)

## Driver notes (Mali-G52 MC2, tested)

| Driver | Result |
| --- | --- |
| System Mali (Vulkan 1.1) + DXVK 2.6 | works, stable |
| Mesa PanVK 26.3 (zenithblue) | loads, fails swapchain (`VK_ERROR_INVALID_EXTERNAL_HANDLE`) |
| PanVK Bifrost (soulexit 1.0.004) | loads, crashes the game |
| PanVK Mesa 27 (JimVulkan r10) | renders, then GPU-hangs the phone |

On this generation of MediaTek kbase devices the PanVK WSI path is not usable;
the system driver + DXVK is the stable Vulkan configuration. The GLES renderer
is the fallback and is close in performance.

## Keys

`keys/debug.pem` / `keys/debug.crt` sign every build so updates install in
place. It is a throwaway key for this hobby APK only.
