"""Sample a common lift-out path; this is not a force or friction simulation.

Run from any directory with numpy, scipy, trimesh and manifold3d installed.
Uses the exported camera and keeper poses shown in mount.scad's assembly.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent


def main():
    clamp = trimesh.load(ROOT / 'stl/clamp.stl')
    clamp.apply_translation([0, 0, -41])
    clamp.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    camera = trimesh.load(ROOT / 'stl/camera.stl')
    camera.apply_translation([0, -1.5, 78.75])
    bodies = [piece for piece in camera.split() if piece.is_volume]
    assert bodies, 'No solid camera components found'
    key = trimesh.load(ROOT / 'stl/key.stl')
    key.apply_translation([0, 0, -6])
    key.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))
    keepers = []
    for side in [-1, 1]:
        keeper = key.copy()
        keeper.apply_translation([side * 31, 18, 67])
        keepers.append(keeper)

    def overlap(a, b):
        return float(abs(trimesh.boolean.intersection([a, b], engine='manifold').volume))

    initial_overlap = sum(overlap(a, b) for a in bodies for b in keepers)
    assert initial_overlap < 0.01, ('camera/keeper interference', initial_overlap)
    samples = []
    for lift in np.arange(0, 60.001, 0.5):
        total = 0.0
        for part in bodies + keepers:
            moving = part.copy()
            moving.apply_translation([0, 0, lift])
            total += overlap(clamp, moving)
        samples.append(dict(lift_mm=float(lift), clamp_interference_mm3=total))
    maximum = max(sample['clamp_interference_mm3'] for sample in samples)
    assert maximum < 0.01, ('lift path interference', maximum)
    final_bottom = float(min(part.bounds[0, 2] for part in bodies + keepers) + 60)
    assert final_bottom > clamp.bounds[1, 2], 'Final pose is not clear above the clamp'
    report = dict(
        pose='Illustrated nominal camera and both keepers lifted together; clamp fixed',
        samples=len(samples), lift_range_mm=[0, 60], step_mm=0.5,
        maximum_clamp_interference_mm3=maximum,
        initial_camera_keeper_interference_mm3=initial_overlap,
        final_moving_bottom_z_mm=final_bottom, clamp_top_z_mm=float(clamp.bounds[1, 2]),
        conclusion='Sampled common vertical escape path has no geometric obstruction',
        limitations=['Discrete samples, not continuous collision detection',
                     'Illustrated nominal geometry, not measured physical hardware',
                     'No friction, preload, deformation, impact or holding-force model'],
        mesh_sha256={name: hashlib.sha256((ROOT / 'stl' / name).read_bytes()).hexdigest()
                     for name in ['clamp.stl', 'camera.stl', 'key.stl']},
    )
    (ROOT / 'evidence/retention.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
