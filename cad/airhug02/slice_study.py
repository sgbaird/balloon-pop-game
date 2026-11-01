"""Compare complete five-part plates with identical profiles; retain support costs.
Usage: python slice_study.py /tmp/squashfs-root/AppRun /tmp/study /path/to/clamp.stl ...
"""

from pathlib import Path
import argparse
import collections, json, math, re, subprocess, zipfile

ROOT = Path(__file__).resolve().parent


def metrics(project, result):
    p = json.loads(result.read_text())
    assert p["return_code"] == 0, p
    plates = p["sliced_plates"]
    assert sum(len(plate["objects"]) for plate in plates) == 5
    assert not any(plate.get("warning_message") for plate in plates)
    with zipfile.ZipFile(project) as z:
        text = "\n".join(
            z.read(f'Metadata/plate_{plate["id"]}.gcode').decode() for plate in plates
        )
    role = ""
    printing = False
    relative = True
    last_e = 0.0
    x = y = 0.0
    lengths = collections.defaultdict(float)
    for line in text.splitlines():
        if line.startswith("; layer num/total_layer_count:"):
            printing = True
        if line.startswith("; FEATURE:"):
            role = line.split(":", 1)[1].strip()
        cmd = line.split(";", 1)[0].strip()
        if cmd == "M83":
            relative = True
        if cmd == "M82":
            relative = False
        vals = {k: float(v) for k, v in re.findall(r"([XYE])(-?\d*\.?\d+)", cmd)}
        if cmd.startswith("G92") and "E" in vals:
            last_e = vals["E"]
        if cmd.startswith(("G0 ", "G1 ", "G2 ", "G3 ")):
            nx = vals.get("X", x)
            ny = vals.get("Y", y)
            delta = vals.get("E", 0) if relative else vals.get("E", last_e) - last_e
            if "E" in vals:
                last_e = vals["E"]
            if printing and delta > 0 and (nx != x or ny != y):
                lengths[role] += delta
            x, y = nx, ny
    grams = {k: v * math.pi * (1.75 / 2) ** 2 * 1.24 / 1000 for k, v in lengths.items()}
    return dict(
        plates=len(plates),
        total_g=sum(plate["filaments"][0]["total_used_g"] for plate in plates),
        seconds=sum(plate["total_predication"] for plate in plates),
        support_g=sum(v for k, v in grams.items() if "Support" in k),
        brim_g=grams.get("Brim", 0),
        extrusion_g_by_feature=grams,
        support_seconds=sum(
            v
            for plate in plates
            for k, v in plate["feature_type_times"].items()
            if "Support" in k
        ),
        warnings=[plate.get("warning_message", "") for plate in plates],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("meshes", type=Path, nargs="+")
    parser.add_argument(
        "--supports", nargs="+", choices=["normal", "tree"], default=["normal", "tree"]
    )
    parser.add_argument(
        "--bridge", action="store_true", help="Omit support under detected bridges"
    )
    args = parser.parse_args()
    app = args.app.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    reports = {}
    for mesh_arg in args.meshes:
        mesh = Path(mesh_arg).resolve()
        for support in args.supports:
            name = f"{mesh.stem}-{support}" + ("-bridge" if args.bridge else "")
            folder = out / name
            folder.mkdir(exist_ok=True)
            config = json.loads((ROOT / "slicer/process.json").read_text())
            config.update(support_type=f"{support}(auto)")
            if args.bridge:
                config["bridge_no_support"] = "1"
            process = folder / "process.json"
            process.write_text(json.dumps(config, indent=2) + "\n")
            with (folder / "slicer.log").open("w") as log:
                subprocess.run(
                    [
                        "xvfb-run",
                        "-a",
                        str(app),
                        "--load-settings",
                        f"{ROOT}/slicer/machine.json;{process}",
                        "--load-filaments",
                        str(ROOT / "slicer/filament.json"),
                        "--orient",
                        "0",
                        "--arrange",
                        "1",
                        "--slice",
                        "0",
                        "--export-3mf",
                        "mount-a1mini-pla.3mf",
                        "--outputdir",
                        str(folder),
                        str(mesh),
                        *[
                            str(ROOT / "stl" / f"{n}.stl")
                            for n in ["screw", "pad", "key", "key"]
                        ],
                    ],
                    cwd=folder,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            reports[name] = metrics(
                folder / "mount-a1mini-pla.3mf", folder / "result.json"
            )
            print(name, json.dumps(reports[name]), flush=True)
            (out / "slices.json").write_text(json.dumps(reports, indent=2) + "\n")


if __name__ == "__main__":
    main()
