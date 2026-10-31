"""Plot CAD alternatives and actual complete-plate slice costs."""

from pathlib import Path
import json
import subprocess
import tempfile
import numpy as np
import trimesh
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from optimize import assembly, slot

ROOT = Path(__file__).resolve().parent


def main():
    slices = json.loads((ROOT / "optimization/slicing.json").read_text())
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "baseline.stl"
        subprocess.run(
            [
                "openscad",
                "-o",
                str(path),
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
            capture_output=True,
        )
        baseline = assembly(trimesh.load(path))
    perforated = baseline.copy()
    study = json.loads((ROOT / "optimization/perforated-study.json").read_text())
    for _, params in study["accepted"]:
        perforated = trimesh.boolean.difference(
            [perforated, slot(*params)], engine="manifold"
        )
    # Keep the reference lip revision as well as the earlier perforated trial.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "lip-baseline.stl"
        subprocess.run(
            [
                "openscad",
                "-o",
                str(path),
                "-D",
                'part="clamp"',
                "-D",
                "clamp_w=48",
                "-D",
                'print_orientation="side"',
                str(ROOT / "mount.scad"),
            ],
            check=True,
            capture_output=True,
        )
        baseline = assembly(trimesh.load(path))
    selected = trimesh.load(ROOT / "stl/clamp.stl")
    selected.apply_translation([0, 0, -19])
    selected.apply_transform(
        trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
    )
    fig = plt.figure(figsize=(12, 8), layout="constrained")
    gs = fig.add_gridspec(2, 3, height_ratios=[1.4, 1])
    meshes = [baseline, perforated, selected]
    names = [
        "Original: 48 mm body",
        "Earlier perforated trial",
        "Selected: 44 mm body",
    ]
    colors = ["#6c8496", "#be8751", "#23968e"]
    for i, (mesh, name, color) in enumerate(zip(meshes, names, colors)):
        # Use the CAD renderer for correct depth occlusion of the thin saddles.
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            mesh.export(folder / "model.stl")
            (folder / "view.scad").write_text(
                f'color("{color}") import("model.stl");\n'
            )
            subprocess.run(
                [
                    "xvfb-run",
                    "-a",
                    "openscad",
                    "-o",
                    str(folder / "view.png"),
                    "--imgsize=800,800",
                    "--camera=130,-210,155,0,8,40",
                    "--viewall",
                    "--autocenter",
                    "--projection=o",
                    "--colorscheme=Tomorrow",
                    str(folder / "view.scad"),
                ],
                check=True,
                capture_output=True,
            )
            picture = plt.imread(folder / "view.png")
        ax = fig.add_subplot(gs[0, i])
        ax.imshow(picture)
        ax.axis("off")
        ax.set_title(name)
        ax.text(
            0.04,
            0.02,
            f"Solid CAD volume: {mesh.volume/1000:.1f} cm³",
            transform=ax.transAxes,
        )
    ax = fig.add_subplot(gs[1, :2])
    key = ["retention-baseline-normal", "optimized-normal", "selected44-front-bridge"]
    labels = ["Original / side down", "Slots / side down", "Selected / front down"]
    support = np.array([slices[k]["support_g"] for k in key])
    total = np.array([slices[k]["total_g"] for k in key])
    ax.barh(
        labels, total - support, color=colors, label="Model, brim and other extrusion"
    )
    ax.barh(
        labels,
        support,
        left=total - support,
        color="#e5b65f",
        label="Supports (from toolpaths)",
    )
    for y, (t, k) in enumerate(zip(total, key)):
        seconds = slices[k]["seconds"]
        minutes = round(seconds / 60)
        ax.text(
            t + 1,
            y,
            f"{t:.1f} g  /  {minutes//60}h {minutes%60:02}m",
            va="center",
            fontsize=10,
        )
    ax.set(
        xlim=(0, 153),
        xlabel="Complete five-part print: filament (g)",
        title="Support costs change the winner",
    )
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, loc="lower right")
    text = fig.add_subplot(gs[1, 2])
    text.axis("off")
    before = slices["retention-baseline-normal"]
    after = slices["selected44-front-bridge"]
    text.text(
        0,
        0.98,
        f"Selected print\n\n{100*(1-after['total_g']/before['total_g']):.1f}% less filament\n{100*(1-after['seconds']/before['seconds']):.1f}% less estimated time\n\nOne plate · all five parts\n5 walls · 30% gyroid · 0.20 mm\nNormal supports enabled\nDetected bridges left unsupported",
        va="top",
        fontsize=11,
    )
    fig.suptitle(
        "AIRHUG mount: CalculiX-guided design and slicer comparison", fontsize=16
    )
    fig.savefig(ROOT / "previews/optimization.png", dpi=150)


if __name__ == "__main__":
    main()
