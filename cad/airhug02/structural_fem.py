"""CalculiX voxel finite-element screening; N, mm, MPa."""

from pathlib import Path
import os, subprocess, json
import numpy as np
import trimesh
from scipy import ndimage


def solve(mesh, folder, pitch=2.0, restraint="spine"):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    lo = (np.floor(mesh.bounds[0] / pitch) - 0.31) * pitch
    hi = (np.ceil(mesh.bounds[1] / pitch) + 0.69) * pitch
    shape = np.rint((hi - lo) / pitch).astype(int)
    ijk = np.indices(shape).reshape(3, -1).T
    centers = lo + (ijk + 0.5) * pitch
    inside = mesh.contains(centers)
    # Keep a fixed offset from integer CAD planes to avoid ambiguous ray tests.
    mask = inside.reshape(tuple(shape))
    labels, n = ndimage.label(mask)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    assert n >= 1
    disconnected_voxels = int(mask.sum() - sizes.max())
    assert disconnected_voxels <= 5, ("disconnected voxel mesh", disconnected_voxels)
    inside = labels.ravel() == sizes.argmax()
    cells = ijk[inside]
    centers = centers[inside]
    # Hexahedral connectivity: standard C3D8 order.
    offsets = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [1, 1, 0],
            [0, 1, 0],
            [0, 0, 1],
            [1, 0, 1],
            [1, 1, 1],
            [0, 1, 1],
        ]
    )
    vertices, inv = np.unique(
        (cells[:, None, :] + offsets).reshape(-1, 3), axis=0, return_inverse=True
    )
    xyz = lo + vertices * pitch
    conn = inv.reshape(-1, 8) + 1
    # Ideal bond to ledge edge, spine patch. Actual friction/contact not modeled.
    fixed = np.flatnonzero(
        (xyz[:, 1] >= -2.01)
        & (xyz[:, 1] <= 0.01)
        & (xyz[:, 2] >= 8)
        & (xyz[:, 2] <= 30)
        & (abs(xyz[:, 0]) <= 8)
    )
    if restraint == "top":
        fixed = np.flatnonzero(
            (abs(xyz[:, 2] - 30) <= pitch / 2)
            & (xyz[:, 1] >= 2)
            & (xyz[:, 1] <= 36)
            & (abs(xyz[:, 0]) <= 22)
        )
    bottom = np.flatnonzero(
        (abs(xyz[:, 0]) <= 10) & (abs(xyz[:, 1] - 24) <= 8) & (xyz[:, 2] <= -8)
    )
    top = np.flatnonzero(
        (abs(xyz[:, 0]) <= 22)
        & (xyz[:, 1] >= 12)
        & (xyz[:, 1] <= 36)
        & (abs(xyz[:, 2] - 30) <= pitch / 2)
    )
    camera = np.flatnonzero(
        (abs(xyz[:, 0]) >= 24)
        & (abs(xyz[:, 0]) <= 36)
        & (abs(xyz[:, 2] - 70) <= pitch / 2)
        & (xyz[:, 1] >= -12)
        & (xyz[:, 1] <= 6)
    )
    assert min(map(len, [fixed, bottom, top, camera])) > 0
    out = ["*HEADING", "AIRHUG idealized solid screening", "*NODE"]
    out += [f"{i+1}," + ",".join(map(str, p)) for i, p in enumerate(xyz)]
    out += ["*ELEMENT,TYPE=C3D8,ELSET=BODY"]
    out += [f"{i+1}," + ",".join(map(str, c)) for i, c in enumerate(conn)]
    out += [
        "*MATERIAL,NAME=PLA",
        "*ELASTIC",
        "1200.,0.35",
        "*SOLID SECTION,ELSET=BODY,MATERIAL=PLA",
        "*BOUNDARY",
    ]
    out += [f"{n+1},1,3" for n in fixed]
    load_cases = [
        ("preload", [(bottom, 2, -100), (top, 2, 100)]),
        ("camera", [(camera, 2, -5), (camera, 1, -5)]),
        ("side", [(camera, 0, 5), (camera, 2, -5)]),
    ]
    for name, forces in load_cases:
        out += ["*STEP", "*STATIC", "*CLOAD,OP=NEW"]
        for nodes, axis, force in forces:
            out += [f"{n+1},{axis+1},{force/len(nodes):.9g}" for n in nodes]
        out += [
            "*NODE PRINT,NSET=NALL",
            "U",
            "*EL PRINT,ELSET=BODY",
            "S,ENER",
            "*END STEP",
        ]
    # Define NALL before steps.
    idx = out.index("*STEP")
    out[idx:idx] = ["*NSET,NSET=NALL,GENERATE", f"1,{len(xyz)},1"]
    deck = "\n".join(out) + "\n"
    input_path = folder / "model.inp"
    log_path = folder / "solver.log"
    cached = (
        input_path.exists()
        and input_path.read_text() == deck
        and log_path.exists()
        and "Job finished" in log_path.read_text()
        and (folder / "model.dat").exists()
    )
    if not cached:
        input_path.write_text(deck)
        with log_path.open("w") as f:
            subprocess.run(
                ["ccx", "model"],
                cwd=folder,
                stdout=f,
                stderr=subprocess.STDOUT,
                env={**os.environ, "OMP_NUM_THREADS": "2"},
                check=True,
            )
    log = (folder / "solver.log").read_text()
    assert "Job finished" in log and "*ERROR" not in log, log[-2000:]
    sections = []
    current = None
    for line in (folder / "model.dat").read_text().splitlines():
        if "displacements (" in line:
            current = {"kind": "u", "data": []}
            sections.append(current)
        elif "stresses (" in line:
            current = {"kind": "s", "data": []}
            sections.append(current)
        elif "internal energy density" in line:
            current = {"kind": "e", "data": []}
            sections.append(current)
        elif current:
            try:
                vals = [float(x) for x in line.split()]
            except ValueError:
                continue
            if vals:
                current["data"].append(vals)
    results = []
    energy = []
    stresses = []
    displacements = []
    for i, name in enumerate(["preload", "camera", "side"]):
        u = np.array(sections[3 * i]["data"])
        s = np.array(sections[3 * i + 1]["data"])
        e = np.array(sections[3 * i + 2]["data"])
        stress = s[:, 2:8]
        stresses.append(stress)
        displacements.append(u[:, 1:4])
        a, b, c, d, e1, f = stress.T
        vm = np.sqrt(
            0.5 * ((a - b) ** 2 + (b - c) ** 2 + (c - a) ** 2)
            + 3 * (d * d + e1 * e1 + f * f)
        )
        en = e[:, 2].reshape(-1, 8).mean(axis=1)
        energy.append(en)
        load_work = sum(
            float(u[nodes, axis + 1].sum()) * force / len(nodes)
            for nodes, axis, force in load_cases[i][1]
        )
        energy_work_error = abs(2 * en.sum() * pitch**3 - load_work) / max(
            abs(load_work), 1e-12
        )
        assert energy_work_error < 1e-4, (
            "energy/work mismatch",
            name,
            energy_work_error,
        )
        results.append(
            dict(
                case=name,
                energy_work_relative_error=energy_work_error,
                max_displacement_mm=float(np.linalg.norm(u[:, 1:4], axis=1).max()),
                max_von_mises_MPa=float(vm.max()),
                p99_von_mises_MPa=float(np.quantile(vm, 0.99)),
                strain_energy_Nmm=float(en.sum() * pitch**3),
            )
        )
    for i, name in [(1, "preload_camera"), (2, "preload_side")]:
        a, b, c, d, e1, f = (stresses[0] + stresses[i]).T
        vm = np.sqrt(
            0.5 * ((a - b) ** 2 + (b - c) ** 2 + (c - a) ** 2)
            + 3 * (d * d + e1 * e1 + f * f)
        )
        results.append(
            dict(
                case=name,
                max_displacement_mm=float(
                    np.linalg.norm(displacements[0] + displacements[i], axis=1).max()
                ),
                max_von_mises_MPa=float(vm.max()),
                p99_von_mises_MPa=float(np.quantile(vm, 0.99)),
            )
        )
    report = dict(
        restraint=restraint,
        discarded_isolated_voxels=disconnected_voxels,
        pitch_mm=pitch,
        nodes=len(xyz),
        elements=len(cells),
        voxel_volume_mm3=len(cells) * pitch**3,
        results=results,
    )
    (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    np.savez_compressed(
        folder / "field.npz", centers=centers, energy=np.array(energy), xyz=xyz
    )
    return report, centers, np.array(energy)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pitch", type=float, default=1.5)
    parser.add_argument(
        "--orientation", choices=["assembly", "side", "front"], default="front"
    )
    parser.add_argument("--restraint", choices=["top", "spine"], default="top")
    args = parser.parse_args()
    model = trimesh.load(args.mesh)
    if args.orientation == "side":
        model.apply_translation([0, 0, -41])
        model.apply_transform(
            trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0])
        )
    elif args.orientation == "front":
        model.apply_translation([0, 0, -19])
        model.apply_transform(
            trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
        )
    print(
        json.dumps(
            solve(model, args.output, pitch=args.pitch, restraint=args.restraint)[0],
            indent=2,
        )
    )
