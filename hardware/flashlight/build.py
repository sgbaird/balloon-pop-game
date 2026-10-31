"""Export and validate the supplied OpenSCAD models. Run from any directory.
Requires OpenSCAD on PATH; verification requires numpy and trimesh.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import argparse
import subprocess

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'stl'

def export(job):
    name, settings = job
    command = ['openscad', '-o', str(OUT / (name + '.stl'))]
    for key, value in settings.items():
        command += ['-D', f'{key}={json.dumps(value)}']
    result = subprocess.run(command + [str(ROOT / 'flashlight.scad')], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(name + '\n' + result.stderr)
    return name

def main():
    import numpy as np
    import trimesh
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only', action='store_true', help='Validate existing STLs without running OpenSCAD')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    jobs = [('flashlight_reference', {'part': 'reference'})]
    for mount, clearance in [('flex', .30), ('press', -.10), ('strap', .60)]:
        for shape in ['circle', 'square', 'triangle', 'cross', 'filled']:
            jobs.append((f'{mount}_{shape}', dict(part='cover', mount=mount,
                         aperture=shape, clearance=clearance)))
    for clearance in [-.2, -.1, 0, .2, .4, .6]:
        name = f'fit_{clearance:+.1f}'.replace('.', 'p')
        jobs.append((name, dict(part='coupon', mount='press', clearance=clearance)))
    jobs.append(('loose_diffuser_disk', dict(part='disk')))
    if not args.validate_only:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(export, jobs))
    report = {}
    for name, _ in jobs:
        mesh = trimesh.load_mesh(OUT / (name + '.stl'))
        # Store compact binary STL, then verify the actual serialized geometry.
        mesh.export(OUT / (name + '.stl'), file_type='stl')
        mesh = trimesh.load_mesh(OUT / (name + '.stl'))
        components = mesh.split()
        assert mesh.is_watertight and mesh.is_volume, name
        assert len(components) == 1, (name, len(components))
        assert abs(mesh.bounds[0, 2]) < .001, (name, mesh.bounds)
        # Measure the optical face itself, not just the outer bounding box.
        # Vertical ray at x=18 lies outside all four apertures and inside the bore.
        thickness = None
        if name.startswith(('flex_', 'press_', 'strap_')):
            tri = mesh.triangles
            a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
            v0, v1 = b[:, :2] - a[:, :2], c[:, :2] - a[:, :2]
            den = v0[:, 0]*v1[:, 1] - v1[:, 0]*v0[:, 1]
            def ray_hits(x, y):
                v2 = np.array([x, y]) - a[:, :2]
                valid = np.abs(den) > 1e-10
                u = np.zeros(len(den)); v = u.copy()
                u[valid] = (v2[:, 0]*v1[:, 1] - v1[:, 0]*v2[:, 1])[valid] / den[valid]
                v[valid] = (v0[:, 0]*v2[:, 1] - v2[:, 0]*v0[:, 1])[valid] / den[valid]
                valid &= (u >= 0) & (v >= 0) & (u+v <= 1)
                return np.unique(np.round((a[:, 2]+u*(b[:, 2]-a[:, 2])+v*(c[:, 2]-a[:, 2]))[valid], 5))
            face_hits = ray_hits(18, .123)
            expected = .2 if name.endswith('_filled') else 1.2
            assert len(face_hits) == 2 and np.allclose(face_hits, [0, expected]), (name, face_hits)
            center_hits = ray_hits(.123, .234)
            assert len(center_hits) == (2 if name.endswith('_filled') else 0), (name, center_hits)
            thickness = expected
        report[name] = dict(watertight=True, components=1, face_thickness_mm=thickness,
                            size_mm=mesh.extents.round(3).tolist(),
                            volume_mm3=round(float(mesh.volume), 3))
    (ROOT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Validated {len(jobs)} closed, single-component meshes; report: validation.json')

if __name__ == '__main__':
    main()
