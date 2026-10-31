"""Render the previous solid frame and current curved frame from actual CAD."""
from pathlib import Path
import json
import subprocess
import tempfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent


def main():
    study = json.loads((ROOT / 'optimization/sculpted.json').read_text())
    fig, axes = plt.subplots(1, 3, figsize=(12, 5.8), layout='constrained')
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        for ax, label, sculpted, camera in zip(
            axes,
            ['Previous solid frame', 'Curved jaws and open side frames', 'Spine and upright ribs'],
            [False, True, True],
            ['-140,220,140,0,6,39', '-140,220,140,0,6,39', '145,-220,145,0,6,39'],
        ):
            mesh_path = folder / 'model.stl'
            subprocess.run(['openscad', '-o', str(mesh_path), '-D', 'part="clamp"',
                            '-D', f'sculpted={str(sculpted).lower()}', str(ROOT / 'mount.scad')],
                           check=True, capture_output=True)
            mesh = trimesh.load(mesh_path)
            mesh.apply_translation([0, 0, -19])
            mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2, [1,0,0]))
            mesh.export(mesh_path)
            view = folder / 'view.scad'
            view.write_text(f'color("#54a9b4") import("{mesh_path}");\n')
            picture = folder / 'view.png'
            subprocess.run(['xvfb-run', '-a', 'openscad', '-o', str(picture),
                            '--imgsize=700,760', '--camera='+camera, '--viewall', '--autocenter',
                            '--projection=o', '--colorscheme=Tomorrow', str(view)],
                           check=True, capture_output=True)
            ax.imshow(plt.imread(picture))
            ax.axis('off')
            ax.set_title(label, fontsize=11)
            ax.text(.5, -.02, f'Solid CAD: {mesh.volume/1000:.1f} cm³',
                    transform=ax.transAxes, ha='center', fontsize=10)
    m = study['selected_slice']
    minutes = round(m['seconds']/60)
    peak = max(r['max_von_mises_MPa'] for r in study['selected_fem']['1.0']['results'])
    fig.suptitle('AIRHUG mount · curved frame + 10 mm side lips', fontsize=15)
    fig.text(.5, .04, f"One A1 mini plate · {m['total_g']:.1f} g incl. supports · {minutes//60} h {minutes%60:02} min\n"
             f"1 mm CalculiX screen: {peak:.2f} MPa peak · physical fit, strength and retention untested",
             ha='center', fontsize=10)
    fig.savefig(ROOT / 'previews/sculpted-frame.png', dpi=140)


if __name__ == '__main__':
    main()
