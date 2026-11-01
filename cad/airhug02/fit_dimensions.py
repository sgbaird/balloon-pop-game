"""Joint perspective fit of two housing rims, with fixed width and focal sweeps.

python cad/airhug02/fit_dimensions.py /path/to/source.mp4
Requires NumPy, SciPy, OpenCV and Pillow. Does not update CAD or print files.
Annotations and source hash are committed; video stays outside the repository.
"""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parent


def rim(height, depth=0, width=65):
    # Equal arc-length sampling, joined by exact line segments in the loss.
    a = np.linspace(-np.pi / 2, np.pi / 2, 49)
    half, radius = (width - height) / 2, height / 2
    x = np.r_[half + radius * np.cos(a), -half - radius * np.cos(a)]
    y = np.r_[radius * np.sin(a), -radius * np.sin(a)]
    return np.c_[x, y, np.full(len(x), depth)]


def project(points, pose, focal):
    p = Rotation.from_rotvec(pose[:3]).apply(points) + pose[3:]
    return p[:, :2] / p[:, 2, None] * focal + [540, 960]


def distances(observed, curve):
    # Continuous point-to-segment distances avoid the old nearest-vertex bias.
    start = curve
    edge = np.roll(curve, -1, axis=0) - start
    delta = np.asarray(observed)[:, None, :] - start
    t = np.clip(np.sum(delta * edge, axis=2) / np.sum(edge * edge, axis=1), 0, 1)
    residual = delta - t[:, :, None] * edge
    idx = np.argmin(np.sum(residual**2, axis=2), axis=1)
    return residual[np.arange(len(observed)), idx].ravel()


def frame_residual(frame, shape, pose, focal):
    result = []
    for name, z in [("rear", 0), ("front", shape[1])]:
        if frame[name]:
            result.extend(
                distances(frame[name], project(rim(shape[0], z), pose, focal))
            )
    return np.array(result)


def initial_pose(frame, focal, tilt):
    points = np.array(frame["rear"] + frame["front"])
    centre = np.mean(points, axis=0)
    scale = np.max(np.ptp(points, axis=0)) / 60
    rot = Rotation.from_euler(
        "xyz", [tilt, 0, frame["angle_deg"]], degrees=True
    ).as_rotvec()
    return np.r_[rot, (centre - [540, 960]) / scale, focal / scale]


def fit(frames, focal, fixed=None, start=None, anchor_pose=None):
    matches = json.loads((ROOT / "evidence/rear-matches.json").read_text())["matches"]

    def matrix(pose):
        rotation = Rotation.from_rotvec(pose[:3]).as_matrix()
        return (
            np.array([[focal, 0, 540], [0, focal, 960], [0, 0, 1]])
            @ np.c_[rotation[:, :2], pose[3:]]
        )

    def correspondence_residual(v):
        indices = {f["second"]: j for j, f in enumerate(frames)}
        if 36 in indices:
            j = indices[36]
            reference = v[2 + 6 * j : 8 + 6 * j]
        elif anchor_pose is not None:
            reference = anchor_pose
        else:
            return []
        residual = []
        inverse = np.linalg.inv(matrix(reference))
        for pair in matches:
            if pair["second"] not in indices:
                continue
            j = indices[pair["second"]]
            pixels = np.array(pair["reference_pixels"])
            plane = np.c_[pixels, np.ones(len(pixels))] @ inverse.T
            q = plane @ matrix(v[2 + 6 * j : 8 + 6 * j]).T
            residual.extend((q[:, :2] / q[:, 2, None] - pair["pixels"]).ravel())
        return residual

    best = None
    if start is None:
        shape = np.array([16.0, 25.0]) if fixed is None else np.array(fixed)
        seeds = []
        alternatives = []
        for frame in frames:
            candidates = []
            for tilt in [-145, -90, -45, 0, 45, 90, 145]:
                for yaw in [-35, 0, 35]:
                    pose = initial_pose(frame, focal, tilt)
                    pose[:3] = Rotation.from_euler(
                        "xyz", [tilt, yaw, frame["angle_deg"]], degrees=True
                    ).as_rotvec()
                    result = least_squares(
                        lambda p: frame_residual(frame, shape, p, focal),
                        pose,
                        bounds=([-np.inf] * 5 + [40], [np.inf] * 6),
                        loss="soft_l1",
                        f_scale=2,
                        max_nfev=120,
                    )
                    candidates.append(result)
            best_pose = min(candidates, key=lambda q: q.cost).x
            best_pose[:3] = Rotation.from_rotvec(best_pose[:3]).as_rotvec()
            seeds.append(best_pose)
            alternatives.append([q.x for q in candidates])
        indices = {f["second"]: j for j, f in enumerate(frames)}
        reference = seeds[indices[36]] if 36 in indices else anchor_pose
        if reference is not None:
            inverse = np.linalg.inv(matrix(reference))
            for j, frame in enumerate(frames):
                pair = next(
                    (m for m in matches if m["second"] == frame["second"]), None
                )
                if pair is None:
                    continue
                pixels = np.array(pair["reference_pixels"])
                plane = np.c_[pixels, np.ones(len(pixels))] @ inverse.T

                def aligned(p):
                    q = plane @ matrix(p).T
                    return np.r_[
                        frame_residual(frame, shape, p, focal),
                        (q[:, :2] / q[:, 2, None] - pair["pixels"]).ravel(),
                    ]

                candidates = []
                for p in alternatives[j]:
                    p = p.copy()
                    p[:3] = Rotation.from_rotvec(p[:3]).as_rotvec()
                    q = least_squares(
                        aligned,
                        p,
                        loss="soft_l1",
                        f_scale=2,
                        max_nfev=180,
                        bounds=([-np.inf] * 5 + [40], [np.inf] * 6),
                    )
                    candidates.append(q)
                seeds[j] = min(candidates, key=lambda q: q.cost).x
                seeds[j][:3] = Rotation.from_rotvec(seeds[j][:3]).as_rotvec()
        starts = [np.r_[shape, np.concatenate(seeds)]]
        # Rear-face homographies leave a handedness ambiguity. Try both
        # normals before interpreting the separation of the two rims.
        flipped = starts[0].copy()
        for j in range(len(frames)):
            rotation = Rotation.from_rotvec(flipped[2 + 6 * j : 5 + 6 * j]).as_matrix()
            flipped[2 + 6 * j : 5 + 6 * j] = Rotation.from_matrix(
                rotation @ np.diag([1, -1, -1])
            ).as_rotvec()
        starts.append(flipped)
    else:
        starts = [start]
    for given in starts:
        x = given.copy()
        if fixed is not None:
            x[:2] = fixed

        def residual(v):
            shape = v[:2] if fixed is None else fixed
            return np.r_[
                np.concatenate(
                    [
                        frame_residual(f, shape, v[2 + 6 * j : 8 + 6 * j], focal)
                        for j, f in enumerate(frames)
                    ]
                ),
                correspondence_residual(v),
            ]

        lower = [8, 4] + [-np.inf] * (len(x) - 2)
        upper = [30, 45] + [np.inf] * (len(x) - 2)
        for j in range(len(frames)):
            lower[7 + 6 * j] = (
                40  # positive optical-axis translation; see depth checks in report
            )
        if fixed is None:
            result = least_squares(
                residual,
                x,
                bounds=(lower, upper),
                loss="soft_l1",
                f_scale=2,
                max_nfev=400,
                ftol=1e-7,
            )
        else:
            result = least_squares(
                lambda p: residual(np.r_[fixed, p]),
                x[2:],
                bounds=(lower[2:], upper[2:]),
                loss="soft_l1",
                f_scale=2,
                max_nfev=400,
                ftol=1e-7,
            )
            result.x = np.r_[fixed, result.x]
        if best is None or result.cost < best.cost:
            best = result
    shape = best.x[:2] if fixed is None else np.asarray(fixed)
    best.x[:2] = shape
    raw = [
        frame_residual(f, shape, best.x[2 + 6 * j : 8 + 6 * j], focal)
        for j, f in enumerate(frames)
    ]
    rms = [float(np.sqrt(np.mean(np.sum(r.reshape(-1, 2) ** 2, axis=1)))) for r in raw]
    return best.x, rms


def font(size):
    return ImageFont.truetype("DejaVuSans.ttf", size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    source = json.loads((ROOT / "evidence/source.json").read_text())
    if hashlib.sha256(args.video.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("Video does not match committed source SHA-256")
    data = json.loads((ROOT / "evidence/dimension-landmarks.json").read_text())
    train = [f for f in data["frames"] if f["role"] == "train"]
    holdout = [f for f in data["frames"] if f["role"] == "holdout"]
    sweep = []
    solutions = {}
    for focal in [900, 1400, 2200]:
        v, errors = fit(train, focal)
        solutions[focal] = v
        sweep.append(
            dict(
                focal_px_assumed=focal,
                height_mm=float(v[0]),
                depth_mm=float(v[1]),
                frame_rms_px=errors,
                poses=[v[2 + 6 * j : 8 + 6 * j].tolist() for j in range(len(train))],
            )
        )
        print(f"f={focal}: H,D={v[:2]}, RMS={errors}", flush=True)
    v = solutions[1400]
    old, old_errors = fit(train, 1400, fixed=[16.1, 10])
    held, held_errors = fit(holdout, 1400, fixed=v[:2], anchor_pose=v[2:8])
    old_held, old_held_errors = fit(
        holdout, 1400, fixed=[16.1, 10], anchor_pose=old[2:8]
    )
    # Leave-one-view-out refits assess dependence on the informative side view.
    leave_out = []
    for omit in range(len(train)):
        subset = [f for j, f in enumerate(train) if j != omit]
        seed = np.r_[
            v[:2],
            np.concatenate(
                [v[2 + 6 * j : 8 + 6 * j] for j in range(len(train)) if j != omit]
            ),
        ]
        q, e = fit(subset, 1400, start=seed)
        leave_out.append(
            dict(
                omitted_second=train[omit]["second"],
                height_mm=float(q[0]),
                depth_mm=float(q[1]),
            )
        )
    report = dict(
        method="Robust joint 3D capsule front/rear rim fit; continuous point-to-segment residuals; 21 per-frame initial normal/tilt guesses, lettering feature correspondences; shared height/depth; width=65 mm scale assumption. Holdout changes only pose.",
        acceptance="DIAGNOSTIC ONLY: not accepted as replacement CAD dimensions. Assess held-out error and leave-one-view-out sensitivity before use.",
        source_sha256=source["sha256"],
        frame_size=[1080, 1920],
        width_mm_assumed=65,
        train_seconds=[f["second"] for f in train],
        sensitivity=sweep,
        leave_one_view_out=leave_out,
        baseline_dimensions_mm=[65, 16.1, 10],
        baseline_frame_rms_px=old_errors,
        holdout_seconds=[f["second"] for f in holdout],
        holdout_frame_rms_px=held_errors,
        baseline_holdout_frame_rms_px=old_held_errors,
        limitations=[
            "Manual outlines and ideal extruded capsule; real bevels and cover differ.",
            "Width and focal length are assumptions; all lengths scale linearly with width.",
            "Rim labels do not solve the clip, hinge or housing-to-tape plane offset.",
            "RMS is annotation agreement, not a physical measurement tolerance.",
        ],
    )
    report["accepted_for_cad"] = False
    report["rejection_reasons"] = [
        "No independently measured housing depth or clip envelope.",
        "Partial rims, bevels and planar pose ambiguity remain; diagnostic fit is not a measured tolerance.",
    ]
    if held_errors[0] >= old_held_errors[0]:
        report["rejection_reasons"].append(
            "Candidate is worse than the baseline on the held-out silhouette."
        )
    if np.ptp([r["depth_mm"] for r in leave_out]) > 2:
        report["rejection_reasons"].append(
            "Removing one training view changes fitted depth by more than 2 mm."
        )
    report["leave_one_view_out_note"] = (
        "Warm-started local refits at 1400 px; sensitivity diagnostic, not confidence intervals."
    )
    report["matched_rear_feature_counts"] = {
        str(m["second"]): len(m["pixels"])
        for m in json.loads((ROOT / "evidence/rear-matches.json").read_text())[
            "matches"
        ]
    }
    report["positive_camera_depths"] = all(
        np.min((Rotation.from_rotvec(pose[:3]).apply(rim(vv[0], z)) + pose[3:])[:, 2])
        > 0
        for vv in solutions.values()
        for j in range(len(train))
        for pose in [vv[2 + 6 * j : 8 + 6 * j]]
        for z in [0, vv[1]]
    )
    if not report["positive_camera_depths"]:
        raise ValueError("Fit projects housing points behind phone")
    (ROOT / "evidence/dimensions.json").write_text(json.dumps(report, indent=2) + "\n")
    cap = cv2.VideoCapture(str(args.video))
    out = Image.new("RGB", (1200, 1000), "#202630")
    draw = ImageDraw.Draw(out)
    draw.text(
        (20, 12),
        "Diagnostic fit only: housing dimensions are not validated",
        font=font(23),
        fill="white",
    )
    for i, (frame, pose, baseline) in enumerate(
        [
            (f, v[2 + 6 * j : 8 + 6 * j], old[2 + 6 * j : 8 + 6 * j])
            for j, f in enumerate(train)
        ]
        + [(holdout[0], held[2:8], old_held[2:8])]
    ):
        cap.set(cv2.CAP_PROP_POS_MSEC, frame["second"] * 1000)
        ok, bgr = cap.read()
        if not ok or bgr.shape[:2] != (1920, 1080):
            raise ValueError("Expected autorotated 1080x1920 frame")
        im = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(im)
        for shape, p, colours in [
            (old[:2], baseline, ["#ff677d"] * 2),
            (v[:2], pose, ["#00e5ff", "#ffcc55"]),
        ]:
            for z, c in zip([0, shape[1]], colours):
                q = project(rim(shape[0], z), p, 1400)
                d.line([tuple(t) for t in np.vstack([q, q[0]])], fill=c, width=3)
        points = np.array(frame["rear"] + frame["front"])
        lo = points.min(axis=0) - [60, 50]
        hi = points.max(axis=0) + [60, 50]
        box = tuple(np.r_[lo, hi].astype(int))
        im = im.crop(box)
        im.thumbnail((390, 400))
        x = (i % 3) * 400
        y = 65 + (i // 3) * 450
        out.paste(im, (x, y + 35))
        draw.text(
            (x + 12, y),
            f"{frame['second']} s ({frame['role']})",
            font=font(18),
            fill="white",
        )
    draw.text(
        (20, 945),
        "Cyan: rear rim   Yellow: front rim   Red: old 10 mm depth (pose refitted)",
        font=font(19),
        fill="white",
    )
    draw.text(
        (20, 974),
        "Rejected as a dimensional correction: see held-out errors and view sensitivity in dimensions.json.",
        font=font(16),
        fill="#c4ced8",
    )
    out.save(ROOT / "previews/dimension-fit.png")
    cap.release()


if __name__ == "__main__":
    main()
