# AIRHUG 02: revised single-plate corner mount

Download [mount-a1mini-pla.3mf](slicer/mount/mount-a1mini-pla.3mf) for the
**photo-informed revision**. It contains sliced G-code for one A1 mini plate:
**one clamp, one screw, one pressure pad and two tapered keepers**. No separate
fit-check print or metal hardware is required. Bambu estimates **118 g / 4 h 15 min**,
including supports and brims. Assembly and support removal are
required after printing; this is not a print-in-place mechanism.

Use **A1 mini / 0.4 mm nozzle / Generic PLA / Textured PEI plate**. Open the project
in Bambu Studio and confirm those match your setup. Normal removable PLA supports
and 5 mm outer brims are enabled; no AMS is needed. All five parts are included
even if you keep using the screw you already printed. Do not scale the project.

![Revised cradle and nominal camera on an example ledge](previews/assembly.png)

## What changed and why

The [five-photo audit](DIMENSIONS.md) supports a nominal housing near
**70 × 17.5 × 25 mm**, replacing the incorrect 65 × 16.1 × 10 mm model.
The reference camera now illustrates an exposed left lens, cover shifted right,
and folded clip. Hidden details and cover travel remain approximate.

The new saddles have **76 mm clear width and 32 mm toe-to-back opening**,
a flat support floor and a front toe only 0.6 mm above it, below the bezel. The optical face and top stay open.
The middle leaves a **45 mm wide** opening behind the housing for the original
clip and cable. Through-slots let the two long keepers slide down behind the
body; their **1–11 mm taper over 36 mm** takes up depth differences. Their top
caps are handles, not a positive latch. They retain the camera by friction.
The camera need not match a tightly fitted capsule cavity.

The female thread's radial allowance is reduced from **0.35 to 0.25 mm** based
on your slightly loose fit report. The screw geometry stays the same, so your
existing screw is reusable. No detents or bumps were added: thread preload
comes from tightening against the pressure pad. This modest change does not
establish holding force or long-term resistance to loosening. The pressure-pad
socket is widened to clear the screw shoulder when its tip bears on the socket
roof; a separate seated-pad intersection check covers this.

Computer checks cover **27 housing scenarios**: widths 66/70/74 mm, heights
16/18/20 mm and depths 23/25/28 mm, with the body front at Y = −14 mm and its
bottom at Z = 70 mm. They check housing/clamp intersection and available keeper
travel, plus a separate 44 × 55 × 27 mm clip keepout. These are chosen design
scenarios around the photo estimates, **not measured tolerance bounds**. They
do not verify the actual clip shape, cover travel, friction or physical fit.
The open space between end stops also permits some lateral play; centre the
housing before seating the keepers. Small removable tape pads can take up
residual side play if necessary.

## Print and assemble

![Actual extrusion paths from the revised single plate](previews/toolpaths.png)

1. Print the complete mount plate. Let it cool, then remove brims and supports,
   especially from the female thread, keeper slots, cradle and pressure-pad
   socket. Do not drive the screw through support debris.
2. Start the screw by hand through the lower jaw and run it several turns.
   If it binds, clear debris and check the thread; do not force it. Place the
   loose pad on its tip, **socket down**. The screw is a custom 16 mm major,
   4 mm pitch trapezoidal thread, not an ISO M16.
3. Slide the clamp onto the ledge until the spine meets the lip and the left
   stop meets the jamb (camera centre 41 mm from the jamb). It needs **38 mm clear reach** above and below the
   ledge and a roughly **10–25 mm thick** ledge. Hand-tighten lightly with at
   least two full turns engaged. Check the clamp's grip before adding the camera.
4. Fold the camera's existing clip into the centre opening, keeping the cable
   free. Lower the housing onto the saddles, with the lens facing away from
   the ledge. The floor is 40 mm above the ledge surface; the nominal optical
   centre is about 49 mm above it. No pan/tilt joint is provided.
5. Insert a keeper at each rear slot, **thin tip down, flat back against the
   rear wall, cap projecting toward the camera**. Alternate gentle pressure on
   the two caps until play is removed. Insertion depth varies with the real
   housing; the illustration is an example, not an insertion-depth target.
   Do not force them or crush the shell. Pull the caps up to remove.
6. Check the full cover motion and live image, then gently check for rocking
   and lift. If the camera or clamp moves, correct the fit before leaving it
   installed. Route cable slack so it cannot tug the camera. Mark the contact
   position and recheck the saved projected-screen corners after reinstalling.

![Updated assembly sequence](previews/assembly.gif)

The goal is one print job with enough adjustment to accommodate the photo
uncertainty. **A first-print physical fit cannot be guaranteed remotely.** The
real camera, ledge, clamp holding force, print quality and PLA creep have not
been tested. Keep it away from projector exhaust.

`corner_side=-1` selects the supplied left stop; `+1` selects right; `0` removes
it. Any change needs regeneration and slicing. The floor/clearances are defined
in [mount.scad](mount.scad). Historical face-only fits and the old animation in
previous commits describe the superseded prototype, not proof of this fit.

## Fit-check pieces already printed

Your original printed gauges have **65.6 mm width and 10.6 mm depth openings**;
they describe the rejected dimensions. Keep the screw; do not force those gauges
onto the housing. The newly regenerated [optional fit-check plate](slicer/fit-check/fit-check-a1mini-pla.3mf)
has **70.6 mm width and 25.6 mm depth openings**, and the revised female thread.
It is not required before this complete plate and does not represent the larger
adjustable cradle openings. Its depth gauge may be too small for the upper end
of the 24–26 mm photo estimates.

![Optional revised gauges; not the already printed originals](previews/fit-check-guide.png)

## Reproduce and inspect

Used OpenSCAD 2021.01 and official
[Bambu Studio 02.08.02.61 Ubuntu 24.04 AppImage](https://github.com/bambulab/BambuStudio/releases/tag/v02.08.02.61),
extracted under `/tmp`. Scripts do not download installers automatically.

```bash
python -m pip install numpy scipy pillow matplotlib opencv-python-headless trimesh manifold3d shapely mapbox-earcut
python cad/airhug02/build.py /tmp/squashfs-root/AppRun
python cad/airhug02/validate.py
python cad/airhug02/preview_toolpaths.py
python cad/airhug02/preview_fit_check.py
python cad/airhug02/animate_assembly.py
python -m unittest discover -s cad/airhug02 -p 'test_*.py'
python -m py_compile *.py cad/airhug02/*.py
```

[Validation report](evidence/validation.json) records mesh topology, independent
housing scenarios, clip keepout, nominal reference-camera intersection, modeled
thread clearance over 15 mm of travel, seated-pad clearance, single-plate object inventory/bounds, embedded machine/PLA
settings, slice estimates and artifact hashes. Slicer success is not a print
or hardware test. Profile snapshots are in `slicer/`: 0.20 mm layers, five walls,
30% gyroid infill, five top/bottom layers and normal supports, using manufacturer
PLA temperatures/cooling/motion. Actual extrusion paths are plotted because GUI
thumbnails are unavailable headlessly. No game or camera/projector calibration
was run.

Bambu profile snapshots and embedded profile data derive from Bambu Studio
02.08.02.61, copyright Bambu Lab and contributors, under AGPL-3.0; see
[slicer/BambuStudio-LICENSE.txt](slicer/BambuStudio-LICENSE.txt) and
[matching upstream source](https://github.com/bambulab/BambuStudio/tree/v02.08.02.61/resources/profiles/BBL).
New CAD and helper scripts use the repository's license.
