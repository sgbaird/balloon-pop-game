"""Audit the width scale independently of the 3D outline fitting.

Usage: python cad/airhug02/audit_ruler.py /path/to/video.mp4
Fits a 1D projective ruler, not a metric rectification of the entire scene.
"""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    source = json.loads((ROOT / "evidence/source.json").read_text())
    if hashlib.sha256(args.video.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("Video does not match source hash")
    data = json.loads((ROOT / "evidence/ruler-landmarks.json").read_text())
    points = np.array([t["pixel"] for t in data["ticks"]], float)
    mm = np.array([t["mm"] for t in data["ticks"]], float)
    centre = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - centre, full_matrices=False)
    axis = vt[0]
    positions = (points - centre) @ axis

    # Normalize the abscissa for numerical conditioning.
    def evaluate(coeff, p):
        u = p / 200
        return (coeff[0] * u + coeff[1]) / (coeff[2] * u + 1)

    initial = [np.polyfit(positions / 200, mm, 1)[0], mm.mean(), 0]
    fit = least_squares(lambda c: evaluate(c, positions) - mm, initial)
    endpoints = np.array(data["housing_width_endpoints"])
    reads = evaluate(fit.x, (endpoints - centre) @ axis)
    apparent = float(abs(np.diff(reads)[0]))
    # Leave-one-tick-out prediction exposes annotation/fit inconsistency.
    loo = []
    for i in range(len(mm)):
        keep = np.arange(len(mm)) != i
        q = least_squares(lambda c: evaluate(c, positions[keep]) - mm[keep], fit.x)
        loo.append(float(evaluate(q.x, positions[i]) - mm[i]))
    report = dict(
        method=data["method"],
        apparent_width_mm=apparent,
        endpoint_ruler_reads_mm=reads.tolist(),
        ruler_tick_rms_mm=float(
            np.sqrt(np.mean((evaluate(fit.x, positions) - mm) ** 2))
        ),
        leave_one_tick_out_error_mm=loo,
        width_scale_scenarios_mm=[
            apparent * s for s in data["plane_and_axis_scale_scenarios"]
        ],
        scenario_note="±10% systematic scale scenarios, NOT a measured confidence interval; hand contact at upper cap, depth mismatch and camera-axis tilt remain.",
        coefficients=fit.x.tolist(),
        ruler_axis=axis.tolist(),
        ruler_origin=centre.tolist(),
    )
    (ROOT / "evidence/ruler-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    cap = cv2.VideoCapture(str(args.video))
    cap.set(cv2.CAP_PROP_POS_MSEC, data["second"] * 1000)
    ok, bgr = cap.read()
    cap.release()
    if not ok or bgr.shape[:2] != (1920, 1080):
        raise ValueError("Wrong frame shape")
    im = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype("DejaVuSans.ttf", 18)
    for t in data["ticks"]:
        x, y = t["pixel"]
        d.line((x - 50, y, x + 15, y), fill="#ffcc55", width=3)
        d.text(
            (x - 115, y - 22),
            str(t["mm"]) + " mm",
            font=font,
            fill="#ffcc55",
            stroke_width=1,
            stroke_fill="black",
        )
    for point, read in zip(endpoints, reads):
        on_ruler = centre + axis * ((point - centre) @ axis)
        d.line([tuple(point), tuple(on_ruler)], fill="#00e5ff", width=3)
        x, y = point
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill="#00e5ff")
    im = im.crop((270, 750, 650, 1240)).resize((570, 735))
    out = Image.new("RGB", (700, 885), "#202630")
    out.paste(im, (65, 70))
    d = ImageDraw.Draw(out)
    d.text(
        (20, 16),
        "51 s: independent metric tape check",
        font=ImageFont.truetype("DejaVuSans.ttf", 23),
        fill="white",
    )
    d.text(
        (20, 815),
        f"Apparent width: {apparent:.1f} mm; working scale remains 65 mm",
        font=font,
        fill="white",
    )
    d.text(
        (20, 845),
        "Plane offset / tilt unresolved; this is not a caliper measurement.",
        font=font,
        fill="#c4ced8",
    )
    out.save(ROOT / "previews/ruler-audit.png")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
