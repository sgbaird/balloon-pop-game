"""Measure the five PR #14 ruler photos independently of the video fit.

python cad/airhug02/audit_photos.py /path/to/photos --download

The optional download writes original bytes as 1.png through 5.png outside the
repository. Without --download, use those existing files. Every input's hash and
size are checked. Requires numpy, scipy, Pillow and matplotlib. This measures
apparent spans, not calibrated 3D dimensions or filming-camera intrinsics.
"""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parent
CYAN = "#00e5ff"
GOLD = "#ffd34e"


def ruler(ticks):
    """Fit mm=(a*u+b)/(c*u+1) on the tape's principal image axis."""
    ticks = np.asarray(ticks, float)
    mm, points = ticks[:, 0], ticks[:, 1:]
    origin = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - origin, full_matrices=False)
    axis = vt[0]
    if (points[-1] - points[0]) @ axis < 0:
        axis = -axis
    u = (points - origin) @ axis / 200

    def evaluate(coeff, positions):
        return (coeff[0] * positions + coeff[1]) / (coeff[2] * positions + 1)

    seed = [np.polyfit(u, mm, 1)[0], mm.mean(), 0]
    coeff = least_squares(lambda c: evaluate(c, u) - mm, seed).x
    loo = []
    for i in range(len(mm)):
        keep = np.arange(len(mm)) != i
        c = least_squares(lambda c: evaluate(c, u[keep]) - mm[keep], coeff).x
        loo.append(float(evaluate(c, u[i]) - mm[i]))

    def read(points):
        return evaluate(coeff, (np.asarray(points) - origin) @ axis / 200)

    return read, origin, axis, dict(
        coefficients=coeff.tolist(),
        origin_px=origin.tolist(),
        axis=axis.tolist(),
        tick_rms_mm=float(np.sqrt(np.mean((read(points) - mm) ** 2))),
        leave_one_tick_out_error_mm=loo,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos", type=Path)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    # Resolve symlinks as well: keep original, large attachments outside the repo.
    folder = args.photos.resolve()
    if folder.is_relative_to(ROOT.parents[1]):
        raise ValueError("Store original photo attachments outside the repository")
    data = json.loads((ROOT / "evidence/photo-landmarks.json").read_text())
    folder.mkdir(parents=True, exist_ok=True)
    images = {}
    for photo in data["photos"]:
        path = folder / f'{photo["number"]}.png'
        if args.download and not path.exists():
            with urlopen(photo["url"], timeout=60) as response:
                content = response.read()
            if hashlib.sha256(content).hexdigest() != photo["sha256"]:
                raise ValueError(f"Attachment hash mismatch: {path.name}")
            path.write_bytes(content)
        if hashlib.sha256(path.read_bytes()).hexdigest() != photo["sha256"]:
            raise ValueError(f"Wrong source photo: {path.name}")
        with Image.open(path) as im:
            if im.size != (4032, 2268):
                raise ValueError(f"Wrong photo dimensions: {path.name}")
            images[photo["number"]] = im.convert("RGB").resize((2048, 1152))

    fig, axes = plt.subplots(3, 2, figsize=(13, 12), facecolor="#182330")
    results = []
    for ax, selection in zip(axes.flat, data["measurements"]):
        read, origin, axis, result = ruler(selection["ticks"])
        ends = np.asarray(selection["endpoints"], float)
        reads = read(ends)
        apparent = abs(float(reads[1] - reads[0]))
        delta = data["endpoint_selection_sensitivity_px"]
        # Move both endpoints independently along the ruler axis. This is ONLY
        # annotation sensitivity, not a bound on systematic geometric error.
        perturbations = [abs(float(np.diff(read(ends + np.array([a, b])[:, None] * axis))[0]))
                         for a in [-delta, delta] for b in [-delta, delta]]
        affine = np.polyfit((np.asarray(selection["ticks"])[:, 1:] - origin) @ axis,
                            np.asarray(selection["ticks"])[:, 0], 1)
        affine_span = abs(float(np.diff((ends - origin) @ axis)[0] * affine[0]))
        result.update(photo=selection["photo"], feature=selection["feature"],
                      endpoint_reads_mm=reads.tolist(), apparent_span_mm=apparent,
                      endpoint_selection_sensitivity_mm=[min(perturbations), max(perturbations)],
                      affine_comparison_span_mm=affine_span,
                      scale_scenarios_mm=[apparent * s for s in data["systematic_scale_scenarios"]])
        results.append(result)
        ax.imshow(images[selection["photo"]])
        for mm, x, y in selection["ticks"]:
            ax.plot(x, y, "+", color=GOLD, markersize=9)
            ax.text(x, y - 25, str(mm), color=GOLD, ha="center", fontsize=9,
                    bbox=dict(facecolor="black", alpha=.65, edgecolor="none", pad=1))
        for end in ends:
            on_tape = origin + axis * ((end - origin) @ axis)
            ax.plot(*np.array([end, on_tape]).T, "--", color=CYAN, linewidth=1)
        ax.plot(*ends.T, color=CYAN, marker="o", markersize=4)
        ax.set_title(f'Photo {selection["photo"]}: apparent {selection["feature"]} {apparent:.1f} mm',
                     color="white", fontsize=12)
        x0, y0, x1, y1 = selection["crop"]
        ax.set_xlim(x0, x1)
        ax.set_ylim(y1, y0)
        ax.set_axis_off()

    front = data["front_ratio"]
    w = np.asarray(front["width_endpoints"], float)
    h = np.asarray(front["height_endpoints"], float)
    long_axis = (w[1] - w[0]) / np.linalg.norm(w[1] - w[0])
    normal = np.array([-long_axis[1], long_axis[0]])
    ratio = abs(float((h[1] - h[0]) @ normal)) / np.linalg.norm(w[1] - w[0])
    widths = [r["apparent_span_mm"] for r in results if r["feature"] == "width"]
    depths = [r["apparent_span_mm"] for r in results if r["feature"] == "depth"]
    heights = [ratio * width for width in widths]
    ax = axes[2, 0]
    ax.imshow(images[2])
    for endpoints in [w, h]:
        ax.plot(*endpoints.T, color=CYAN, marker="o", markersize=4)
    x0, y0, x1, y1 = front["crop"]
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)
    ax.set_axis_off()
    ax.set_title(f'Photo 2: face height / width = {ratio:.3f}', color="white", fontsize=12)
    ax = axes[2, 1]
    ax.set_axis_off()
    ax.text(0, .92, "Independent photo evidence", color="white", fontsize=16, weight="bold")
    ax.text(0, .76, f'Width: {min(widths):.1f}-{max(widths):.1f} mm apparent\n'
            f'Depth: {min(depths):.1f}-{max(depths):.1f} mm apparent\n'
            f'Face height: about {np.mean(heights):.1f} mm, conditional on width',
            color="white", fontsize=13, va="top", linespacing=1.8)
    ax.text(0, .36, "The original 10 mm depth is contradicted.\n"
            "Gold: metric ticks (mm). Cyan: housing spans.\n\n"
            "Tape fit does not remove plane offset, housing tilt\n"
            "or lens distortion. Zoom is not a calibration.\n"
            "These are estimates, not verified print clearances.",
            color="#c5d2e0", fontsize=11, va="top", linespacing=1.6)
    fig.suptitle("AIRHUG 02: new ruler photos vs. original dimension assumptions",
                 color="white", fontsize=18)
    fig.tight_layout(rect=(0, 0, 1, .96), h_pad=2)
    fig.savefig(ROOT / "previews/photo-audit.png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    report = dict(
        method="Independent per-photo 1D projective metric ruler fit; endpoints projected onto tape image axis. No 3D pose fit or physical-fit acceptance.",
        measurements=results,
        frontal_height_to_width_ratio=ratio,
        conditional_height_estimates_mm=heights,
        interpretation="Working envelope near 70 x 17-18 x 25 mm (width x height x depth); rounded photo estimates, not caliper measurements. Existing 65 x 16.1 x 10 mm print geometry is obsolete as a claimed camera fit.",
        limitations=["Tape plane and housing plane are not coincident; no 3D correction.",
                     "Out-of-plane housing rotations and lens distortion are not corrected.",
                     "5% scale scenarios are illustrative, not confidence limits or guaranteed error bounds.",
                     "Endpoint perturbations and tick residuals measure annotation/fit consistency only.",
                     "Front photo has no ruler: face height transfers width from other views and assumes near-frontal pose.",
                     "User reports a distant, zoomed phone view; phone model, lens, zoom and intrinsics are not established by these attachments.",
                     "Clip, hinge, cover travel and mounting envelope still require clearance checks."],
        artifacts_changed="Photo evidence, report and documentation only; existing CAD, STL and sliced 3MFs are not regenerated.",
    )
    (ROOT / "evidence/photo-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    for r in results:
        print(f'Photo {r["photo"]}: {r["feature"]} {r["apparent_span_mm"]:.2f} mm; tick RMS {r["tick_rms_mm"]:.3f} mm')
    print(f'Conditional face height: {np.mean(heights):.2f} mm')


if __name__ == "__main__":
    main()
