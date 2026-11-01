"""Energy-guided discrete topology optimization with printable rounded slots.

Run: python optimize.py /tmp/airhug-optimization
Keeps threads, saddles, stops and exterior dimensions. No random seed or optimiser
service required. CalculiX, numpy, scipy, trimesh, manifold3d, embreex required.
"""

from pathlib import Path
import json, sys, subprocess
import numpy as np
import trimesh
from structural_fem import solve

ROOT = Path(__file__).resolve().parent


def slot(x, y, z, axis, width, length, depth):
    # Capsule long axis local Y, cut direction local Z.
    r = width / 2
    parts = []
    for sign in [-1, 1]:
        a = trimesh.creation.cylinder(radius=r, height=depth, sections=32)
        a.apply_translation([0, sign * (length - width) / 2, 0])
        parts.append(a)
    if length > width:
        parts.append(trimesh.creation.box([width, length - width, depth]))
    cut = trimesh.boolean.union(parts, engine="manifold")
    if axis == "x_y":
        cut.apply_transform(
            trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])
        )
    if axis == "x_z":
        cut.apply_transform(
            trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
        )
        cut.apply_transform(
            trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1])
        )
    if axis == "y":
        cut.apply_transform(
            trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
        )
    cut.apply_translation([x, y, z])
    return cut


def candidates():
    if "--channels" in sys.argv:
        return [
            ("jaw_channel", [0, 23, 35, "x_y", 4, 24, 50]),
            ("spine_channel", [0, -5, 16, "x_z", 4, 24, 50]),
            ("lower_channel", [0, 10, -5, "x_y", 4, 8, 50]),
        ]
    result = []
    for side in [-1, 1]:
        result += [
            (f"lower_{side}", [side * 17, 21, -5, "z", 6, 26, 14]),
            (f"upper_{side}", [side * 16, 23, 35, "z", 8, 22, 14]),
            (f"spine_{side}", [side * 16, -5, 16, "y", 8, 24, 14]),
            (f"upright_{side}", [side * 28, -8, 53, "y", 6, 18, 12]),
        ]
    result += [("upper_center", [0, 23, 35, "z", 12, 22, 14])]
    return result


def assembly(mesh):
    mesh = mesh.copy()
    mesh.apply_translation([0, 0, -41])
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    return mesh


def printable(mesh):
    mesh = mesh.copy()
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))
    mesh.apply_translation([0, 0, 41])
    return mesh


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    baseline_path = out / "baseline.stl"
    subprocess.run(
        [
            "openscad",
            "-o",
            str(baseline_path),
            "-D",
            'part="clamp"',
            "-D",
            "clamp_w=48",
            "-D",
            "side_lip_height=0",
            "-D",
            'print_orientation="side"',
            str(ROOT / "mount.scad"),
        ],
        check=True,
    )
    baseline = assembly(trimesh.load(baseline_path))
    current = baseline.copy()
    report, centers, energy = solve(current, out / "baseline")
    history = [dict(name="baseline", volume_mm3=float(current.volume), **report)]
    remaining = candidates()
    accepted = []
    rejected = []
    while remaining:
        # First-order compliance cost per removed volume; normalize each case
        # so the 100 N preload cannot hide a camera support's load path.
        sensitivity = np.max(
            energy / np.maximum(energy.mean(axis=1)[:, None], 1e-16), axis=0
        )
        choices = []
        for name, params in remaining:
            cut = slot(*params)
            mask = cut.contains(centers)
            if mask.sum():
                choices.append((float(sensitivity[mask].mean()), name, params, cut))
        if not choices:
            break
        score, name, params, cut = min(choices, key=lambda t: t[0])
        remaining = [item for item in remaining if item[0] != name]
        trial = trimesh.boolean.difference([current, cut], engine="manifold")
        assert trial.is_watertight and trial.is_volume
        if len(trial.split()) != 1:
            rejected.append(dict(name=name, reason="disconnected"))
            continue
        check, c, e = solve(trial, out / f"trial-{name}")
        # Screening limits, not experimentally established material allowables.
        passes = all(
            r["max_von_mises_MPa"] < 8
            and r["max_displacement_mm"]
            < (1.2 if r["case"].startswith("preload") else 0.5)
            for r in check["results"]
        )
        entry = dict(
            name=name,
            slot=params,
            score=score,
            volume_mm3=float(trial.volume),
            accepted=passes,
            **check,
        )
        history.append(entry)
        print(json.dumps(entry), flush=True)
        if passes:
            current = trial
            centers = c
            energy = e
            accepted.append([name, params])
            printable(current).export(out / f"candidate-{len(accepted)}.stl")
        else:
            rejected.append(dict(name=name, reason="screening limit"))
    result = dict(
        baseline_commit="005a54c",
        method="Sequential energy-guided rounded-slot insertion, remeshed and re-solved after each insertion",
        accepted=accepted,
        rejected=rejected,
        history=history,
    )
    (out / "optimization.json").write_text(json.dumps(result, indent=2) + "\n")
    (out / "slots.json").write_text(json.dumps(accepted, indent=2) + "\n")
    # Export final and preserve exact decks + reports; bulky DAT stays in /tmp.
    printable(current).export(out / "optimized.stl")
    for pitch in ([] if "--coarse-only" in sys.argv else [1.5, 1.0]):
        for name, mesh in [("baseline", baseline), ("optimized", current)]:
            print(
                name,
                pitch,
                solve(mesh, out / f"{name}-{pitch}", pitch=pitch)[0],
                flush=True,
            )


if __name__ == "__main__":
    main()
