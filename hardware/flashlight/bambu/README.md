# Bambu Studio slicing trial — A1 mini / PLA

**Succeeded on the Ubuntu 24.04 GitHub Actions runner:** installed the official
Bambu Studio **2.8.2.61** Linux AppImage and sliced all **22 printable flashlight
parts**. Each file in [sliced](sliced) contains one part on one plate, the editable
model, resolved printer/material/process settings, and embedded G-code. The
illustrative `flashlight_reference.stl` is excluded.

The models come unchanged from the earlier issue-5 work, commit
[`9131b0f`](https://github.com/sgbaird/balloon-pop-game/commit/9131b0f).
They are included in this branch because that work was not on `main` when this
trial started. See the [design/fit guide](../README.md) before printing.

## Download

Download a raw `.3mf` from [sliced](sliced) and open it in Bambu Studio. Review
the selected printer, filament, bed, and toolpath preview before starting a print.
Use the actual spool's PLA profile if it differs from Generic PLA. These exports
have **no thumbnail images** (see the runner limitation below).

Start with a [fit ring](sliced/fit_+0p6.3mf), working from larger to smaller bores.
After confirming fit, try [flex_circle.3mf](sliced/flex_circle.3mf).
Use opaque PLA for aperture masks; use translucent/natural PLA for the
[filled cover](sliced/flex_filled.3mf) or
[loose diffuser](sliced/loose_diffuser_disk.3mf).

| Parts, one per plate | Layers | Estimated time each | PLA each |
| --- | ---: | ---: | ---: |
| Six `fit_*` rings | 40 | 12m 12s–12m 18s | 2.01–2.04 g |
| Twelve circle/square/triangle/cross covers, all three mounts | 76 | 20m 15s–21m 26s | 4.92–5.18 g |
| Three `*_filled` covers | 71 | 17m 31s–18m 26s | 3.54–3.86 g |
| `loose_diffuser_disk` | **1** | 7m 9s | 0.37 g |

Times include Bambu's startup estimate for **each separate job**. They are slicer
estimates, not measured print times. Exact per-file results, source/output hashes,
and warnings are in [report.json](sliced/report.json).

## Settings and checks

- Machine: **Bambu Lab A1 mini, 0.4 mm stainless steel nozzle**, 180 × 180 × 180 mm.
- Filament: **Generic PLA @BBL A1M**, 1.75 mm, 220 °C nozzle; **Textured PEI Plate**, 65 °C bed.
- Process: **0.20mm Standard @BBL A1M**, with first layer explicitly **0.20 mm**,
  **four wall loops**, **no brim**, and **supports disabled**. Other settings,
  including speeds and 15% nominal sparse infill, come from the bundled presets.
- Original model orientation and scale are retained: optical faces on the bed,
  sleeve openings upward; arrangement only positions parts on the plate.
- Full presets are in [profiles](profiles). `prepare_profiles.py` recursively
  resolves both inheritance and included G-code templates; passing the sparse
  resource JSONs directly is insufficient for Bambu's CLI.

Every export was checked for ZIP integrity, embedded G-code MD5, exact machine,
PLA and process settings, A1 mini model ID `N1`, and plate metadata reporting no
out-of-bed objects or supports. G-code layer markers confirm 0.20 mm increments
and the layer counts above. The three filled covers have bottom-surface infill
on their first layer, followed by sleeve walls rather than another solid face;
the separate disk has exactly one layer. These checks inspect generated files;
they do not establish physical fit or optical transmission.

Bambu records `not_support_traditional_timelapse` warnings in the exports, even
though this run does not enable timelapse. Leave timelapse disabled when printing
these projects on the A1 mini. All slice operations returned success.

## Reproduce on Ubuntu 24.04 x86-64

The application is extracted into a temporary directory, so FUSE is unnecessary.
Run the following from the repository root:

```bash
sudo apt-get update
sudo apt-get install -y xvfb libgstreamer-plugins-base1.0-0 libwebkit2gtk-4.1-0 libosmesa6
mkdir -p /tmp/bambu-issue5
curl -fL https://github.com/bambulab/BambuStudio/releases/download/v02.08.02.61/BambuStudio_ubuntu24.04-v02.08.02.61-20260820225108.AppImage \
  -o /tmp/bambu-issue5/BambuStudio.AppImage
echo 'd501b103fac5424513ec0e8d6bc145fb30719de2c7d94d7320d723740c81a7fd  /tmp/bambu-issue5/BambuStudio.AppImage' | sha256sum -c -
chmod +x /tmp/bambu-issue5/BambuStudio.AppImage
(cd /tmp/bambu-issue5 && ./BambuStudio.AppImage --appimage-extract > extract.log)
python hardware/flashlight/bambu/prepare_profiles.py /tmp/bambu-issue5/squashfs-root
xvfb-run -a python hardware/flashlight/bambu/slice.py \
  --studio /tmp/bambu-issue5/squashfs-root/AppRun
python hardware/flashlight/bambu/slice.py --verify-only
python -m py_compile *.py hardware/flashlight/*.py hardware/flashlight/bambu/*.py
```

The download checksum records the exact binary tested. Regeneration can change
archive hashes through timestamps/internal IDs; `--verify-only` compares the
current artifacts against their saved report. The two helper scripts use Python's
standard library. Slice subprocesses have a five-minute timeout per model and
isolated temporary user settings. No printer connection is required.

`prepare_profiles.py` also copies the bundled machine-model metadata into the
extracted application's `resources/profiles/BBL/machine_full` directory. This
release's CLI reads that location to populate `printer_model_id`; without this
workaround it exports an empty ID despite having the correct A1 mini G-code.

### Runner limitation: thumbnails

The Ubuntu AppImage's thumbnail renderer first failed to connect to Wayland.
Starting a headless Weston compositor got past that step, but OpenGL/GLEW
initialization still failed. Studio nevertheless exported complete model,
settings, and G-code data and returned success. The committed files consistently
omit thumbnails; the report records that fact. The commands above use Xvfb for
the CLI and reproduce slicing without requiring Weston. Thumbnail generation
and GUI interaction were not validated.

No physical printer was connected. Printing, bed adhesion, fit, heat resistance,
light transmission and beam shapes remain untested. The camera/projector game
was not run; repository Python syntax checks passed.

## Upstream sources and licensing

- [Official release and binaries](https://github.com/bambulab/BambuStudio/releases/tag/v02.08.02.61)
- [Official command-line documentation](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage)
- [Bundled BBL presets at this release](https://github.com/bambulab/BambuStudio/tree/v02.08.02.61/resources/profiles/BBL)

The JSON presets are derived from Bambu Studio's bundled resources, with the
changes listed above; their upstream [AGPL-3.0 license](profiles/LICENSE) is
included. The Bambu Studio executable is not committed.
