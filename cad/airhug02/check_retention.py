"""Check side-lip crossings and a common lift-out path; no force/friction model.

Run from any directory with numpy, scipy, trimesh and manifold3d installed.
Uses the exported camera and keeper poses shown in mount.scad's assembly.
"""

import hashlib
import itertools
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
    # Independently construct capsule housings, excluding speculative accessories.
    # After a -4 mm Y translation, the front passes the toe and side lips.
    # Compare seated crossings and crossings just below/above clearance.
    from shapely.geometry import Polygon
    crossings = []
    for w, h, d in itertools.product([66, 70, 74], [16, 18, 20], [23, 25, 28]):
        outline = []
        for centre, angles in [((w-h)/2, np.linspace(-np.pi/2, np.pi/2, 65)),
                               (-(w-h)/2, np.linspace(np.pi/2, 3*np.pi/2, 65))]:
            outline.extend([[centre+h/2*np.cos(a), h/2*np.sin(a)] for a in angles])
        housing = trimesh.creation.extrude_polygon(Polygon(outline), d, engine='earcut')
        housing.apply_transform(np.array([[1,0,0,0],[0,0,1,-14],[0,1,0,70+h/2],[0,0,0,1]]))
        seated = overlap(clamp, housing)
        assert seated < 0.01, (w, h, d, 'seated', seated)
        moved = housing.copy(); moved.apply_translation([0,-4,0])
        blocked = overlap(clamp, moved)
        assert blocked > 0.1, (w, h, d, 'unblocked forward crossing', blocked)
        # End curvature determines the rise needed to clear a 10 mm lip at X=31.
        dx = max(0, 31-(w-h)/2)
        lower_edge = h/2 - np.sqrt((h/2)**2-dx**2)
        required_lift = 10-lower_edge
        assert required_lift > 0.6, (w, h, d, required_lift)
        below = housing.copy(); below.apply_translation([0,-4,required_lift-0.25])
        above = housing.copy(); above.apply_translation([0,-4,required_lift+0.25])
        assert overlap(clamp, below) > 0.001, (w,h,d,'below threshold')
        assert overlap(clamp, above) < 0.01, (w,h,d,'above threshold')
        crossings.append(dict(width=w, height=h, depth=d,
                              seated_interference_mm3=seated,
                              forward_crossing_interference_mm3=blocked,
                              approximate_lift_to_clear_mm=float(required_lift)))
    report = dict(
        pose='Illustrated nominal camera and both keepers lifted together; clamp fixed',
        samples=len(samples), lift_range_mm=[0, 60], step_mm=0.5,
        maximum_clamp_interference_mm3=maximum,
        initial_camera_keeper_interference_mm3=initial_overlap,
        final_moving_bottom_z_mm=final_bottom, clamp_top_z_mm=float(clamp.bounds[1, 2]),
        conclusion='Side lips block seated forward escape; open top still permits deliberate lift-out',
        side_lip_height_mm=10, central_face_opening_mm=62,
        housing_forward_crossings=crossings,
        lift_to_clear_range_mm=[min(s['approximate_lift_to_clear_mm'] for s in crossings),
                                max(s['approximate_lift_to_clear_mm'] for s in crossings)],
        limitations=['Discrete samples, not continuous collision detection',
                     'Illustrated nominal geometry, not measured physical hardware',
                     'Forward crossings assume centred, unrotated housings; no combined escape paths',
                     'No friction, preload, deformation, impact or holding-force model'],
        mesh_sha256={name: hashlib.sha256((ROOT / 'stl' / name).read_bytes()).hexdigest()
                     for name in ['clamp.stl', 'camera.stl', 'key.stl']},
    )
    (ROOT / 'evidence/retention.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
