# Webcam dimension audit after the fit-check feedback

**The original mount's camera fit is unverified. Do not use the existing complete
mount 3MF as a dimensionally corrected print.** The old 65 × 16.1 × 10 mm housing
is a hypothesis, not a measurement. The fit-check pieces already printed remain
useful for checking their actual openings; a successful screw fit says nothing
about the camera envelope.

The original analysis fixed width at 65 mm, adjusted height against two face
outlines, and never optimized depth or the clip. Its 2.10 pixel training error
could not establish that the three-dimensional camera would fit. In particular,
subtracting the original model from its own clamp only established internal CAD
consistency. It did not validate the real hardware.

## What was re-examined

The entire 61-second source was sampled for view selection, with detailed
inspection of the camera, clip and tape views. The scripts verify the original
video's SHA-256 and its autorotated **1080 × 1920** frame size before analysis.
[Video metadata](evidence/video-metadata.json) identifies a **Pixel 9**, but does
not supply lens selection, zoom, stabilization crop or focal length. Knowing the
phone model does not establish its recording intrinsics.

Two separate checks now replace the face-only argument:

1. **Metric tape audit at 51 seconds.** Eight annotated centimetre ticks fit a
   one-dimensional projective ruler. The approximately parallel housing axis
   projects to an apparent **64.6 mm width**. This supports keeping 65 mm as a
   working scale. It does not prove it: the upper cap touches the hand, and the
   housing and tape are at different depths. The small ruler interpolation
   error measures tick consistency, not webcam accuracy. Explicit ±10% scale
   scenarios give 58.2–71.1 mm; these are assumptions, not confidence bounds.
2. **Joint three-dimensional diagnostic at 36, 39, 45 and 57 seconds.** Both
   visible housing rims constrain a shared capsule height and depth, with a
   separate perspective pose per view. Missing/occluded edges are omitted.
   SIFT matches on the rear lettering, with affine stretching for the oblique
   view and RANSAC rejection, constrain relative face poses. Continuous
   point-to-segment distances replace the old nearest-sampled-vertex loss.
   Pose initialization tries 21 tilt combinations per view and both normal
   choices. Focal lengths 900, 1,400 and 2,200 px are tested, with square pixels,
   centered principal point and zero distortion still assumed.

![Independent tape scale check](previews/ruler-audit.png)

## Why the new fit is not a replacement set of dimensions

The extra constraints expose how sensitive the inferred depth is to pose,
partial boundaries and the assumed capsule shape. A candidate that improves
some training contours is insufficient. The **18-second view is excluded from
shape fitting**; only its pose is fitted using the frozen candidate dimensions.
The original dimensions receive the same pose-fitting opportunity. The report
also removes each training view in turn and refits locally to reveal dependence
on a particular view. These are diagnostics, not statistical confidence bounds.

For this run, the focal sweep produced candidate heights of **12.5–13.8 mm**
and depths of **19.1–20.4 mm**, at the assumed 65 mm width.
The 1,400 px candidate's held-out outline RMS was **17.9 pixels**,
versus **30.2 pixels** for the old dimensions. That is an improvement,
but still an imperfect match. Removing the 57-second view changes inferred
depth to **24.3 mm**. The 2 mm sensitivity flag in the report is
a review threshold, not a claimed manufacturing tolerance. These results do
not justify replacing the 10 mm guess with a precise 20 mm claim.

[The numerical report](evidence/dimensions.json) records the focal sweep,
per-view errors, old-model comparison, held-out error, view-removal sensitivity
and explicit rejection reasons. **No new height/depth pair has been accepted
for CAD.** The comparison below deliberately includes imperfect overlays so a
plausible-looking projection cannot stand in for validation. Complete outlines
through fingers, cables and the clip are extrapolations, not observations.

![Diagnostic rim comparison; not accepted as measured dimensions](previews/dimension-fit.png)

| Dimension | Current conclusion | Effect on the existing print |
| --- | --- | --- |
| Housing width | Near 65 mm remains plausible from the tape; plane offset unresolved | 65.6 mm width gauge is still a useful physical check |
| Housing height | Old 16.1 mm value was conditional on pose and width | Existing coupons do not check height |
| Housing depth | Old 10 mm was never fitted; new candidates fail sufficient independent validation | 10.6 mm gauge only tests that particular opening; do not force it |
| Clip, hinge and folded envelope | Still approximate; not reconstructed by the rim fitter | Clip clearance and keeper placement are unverified |
| Ledge and clamp grip | Not determined by this housing analysis | Requires physical contact/grip checks |

The published STL/3MF files, camera render and assembly GIF retain the original
prototype dimensions. They were **not regenerated with an unvalidated candidate**.
The [manufacturer's page](https://airhug.com/products/airhug-02-mini-webcam-without-microphone)
labels its dimensions as *package dimensions*, so those are not used as housing
measurements either.

## Turning the prototype into a measured fit

For a dimensional correction, record the main housing's width, face height and
front-to-back depth, with the cover protrusion recorded separately, plus the
folded clip's width/depth/height and hinge position. A ruler or caliper measurement
of the depth would directly resolve the weakest mounting dimension; additional
oblique silhouettes alone do not do that. Keep the cable and cover travel clear.

For useful follow-up photos, put a metric ruler **alongside the measured face in
the same plane**, show both ends, keep fingers off the outline, and take separate
front and edge views. A short orbit with a stationary camera body and a rigid
printed calibration target would additionally constrain the filming camera's
intrinsics; do not use the AIRHUG's own advertised FOV for that purpose.

Once measured, update `camera_w`, `camera_h` and `camera_d` in `mount.scad`, inspect
the clip clearance and keeper locations, then regenerate and validate the meshes
and both slices. The existing `validate.py` checks the CAD and printer artifacts;
it cannot certify that a camera-sized void matches a real camera.

## Reproduce the audit

```bash
python -m pip install numpy scipy pillow opencv-python-headless
python cad/airhug02/match_rear.py /path/to/video.mp4
python cad/airhug02/audit_ruler.py /path/to/video.mp4
python cad/airhug02/fit_dimensions.py /path/to/video.mp4
python -m unittest discover -s cad/airhug02 -p test_dimensions.py -v
python -m py_compile *.py cad/airhug02/*.py
```

Manual rim selections are in [dimension-landmarks.json](evidence/dimension-landmarks.json),
tape selections in [ruler-landmarks.json](evidence/ruler-landmarks.json), and
feature correspondences in [rear-matches.json](evidence/rear-matches.json).
Synthetic checks verify continuous segment distances, joint shape recovery from
known perspective views and preservation of fixed dimensions during pose fitting.
They test the mathematics, not this webcam's true size. Image overlays and
ruler reports were regenerated from the original video. No new slicing, physical
fit, clamping/load test, game run or camera/projector calibration was performed.
