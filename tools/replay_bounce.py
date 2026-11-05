"""Replay a BALLOON_DEBUG_DIR recording through bounce_ball.py and list the hits.

Run from the repo root:
    python tools/replay_bounce.py <recording dir> [--last N] [--sheet hits.png] [NAME=VALUE ...]

NAME=VALUE overrides a constant in bounce_ball.py (for example SPEED_MIN=4.0 or
"BALL_HUE=(22,42)"), so settings can be compared on the same recording. Uses
projector_calibration.yaml from the current folder. --sheet saves crops around the
first 40 hits (the frame 6 before and the hit frame). The recordings show the room and
the people in it: blur faces before looking at them, and never commit them.
"""
import argparse
import ast
import csv
import os
import sys

import cv2
import numpy as np
import yaml

sys.path.insert(0, os.getcwd())
import bounce_ball as BB  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("recording")
ap.add_argument("--last", type=int, default=None, help="stop after this frame index")
ap.add_argument("--sheet", help="save a contact sheet of hits here")
ap.add_argument("--frames", help="read images from this folder instead (for example a face-blurred copy)")
ap.add_argument("overrides", nargs="*")
a = ap.parse_args()
for kv in a.overrides:
    k, v = kv.split("=", 1)
    setattr(BB, k, type(getattr(BB, k))(ast.literal_eval(v)))

corners = np.float32(yaml.safe_load(open("projector_calibration.yaml"))["projector_points"])
M = cv2.getPerspectiveTransform(corners, np.float32([[0, 0], [1919, 0], [1919, 1079], [0, 1079]]))
det = BB.BounceImpactDetector(corners, (480, 640))
rows = list(csv.DictReader(open(os.path.join(a.recording, "frames.csv"))))
if a.last is not None:
    rows = [r for r in rows if int(r["index"]) <= a.last]
hits = []
for r in rows:
    f = cv2.imread(os.path.join(a.recording, "%06d.jpg" % int(r["index"])))
    if f is None:
        continue
    res = det.update(f, float(r["time"]))
    if res is not None:
        sx, sy = cv2.perspectiveTransform(np.float32([[res[:2]]]), M)[0][0]
        hits.append((int(r["index"]), res, (sx, sy)))
ys = [s[1] for _, _, s in hits]
print("hits: %d in %d frames" % (len(hits), len(rows)))
print("by screen fifth, top to bottom:", np.histogram(ys, bins=[-1e9, 216, 432, 648, 864, 1e9])[0].tolist())
print("frames:", " ".join(str(i) for i, _, _ in hits))

if a.sheet and hits:
    src = a.frames or a.recording
    tiles = []
    for i, (x, y, rr), _ in hits[:40]:
        pair = []
        for j in (max(0, i - 6), i):
            img = cv2.imread(os.path.join(src, "%06d.jpg" % j)).copy()
            cv2.circle(img, (int(x), int(y)), int(rr) + 3, (0, 0, 255), 1)
            x0, y0 = int(min(max(x - 60, 0), 520)), int(min(max(y - 45, 0), 390))
            pair.append(cv2.resize(img[y0:y0 + 90, x0:x0 + 120], (180, 135)))
        t = np.hstack(pair)
        cv2.putText(t, str(i), (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        tiles.append(t)
    while len(tiles) % 5:
        tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(a.sheet, np.vstack([np.hstack(tiles[r:r + 5]) for r in range(0, len(tiles), 5)]))
