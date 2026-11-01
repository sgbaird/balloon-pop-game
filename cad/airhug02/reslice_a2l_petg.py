"""Reslice the existing print meshes with official A2L / Generic PETG presets.

Usage: python cad/airhug02/reslice_a2l_petg.py /tmp/squashfs-root/AppRun
Does not regenerate CAD or overwrite the earlier A1 mini / PLA projects.
"""
import argparse
from pathlib import Path
import subprocess

from build import ROOT, presets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    args = parser.parse_args()
    app = args.app.resolve()
    output = ROOT/'slicer/a2l-petg'
    presets(app, output=output, names={
        'machine': 'Bambu Lab A2L 0.4 nozzle',
        'process': '0.20mm Standard @BBL A2L',
        'filament': 'Generic PETG @BBL A2L',
    })
    for name, models in [
        ('mount', ['clamp', 'screw', 'pad', 'key', 'key']),
        ('fit-check', ['coupon', 'screw']),
    ]:
        folder = output/name
        folder.mkdir(exist_ok=True)
        with (folder/'slicer.log').open('w') as log:
            subprocess.run([
                'xvfb-run', '-a', str(app),
                '--load-settings', f'{output}/machine.json;{output}/process.json',
                '--load-filaments', str(output/'filament.json'),
                '--orient', '0', '--arrange', '1', '--slice', '0',
                '--export-3mf', f'{name}-a2l-petg.3mf', '--outputdir', str(folder),
                *[str(ROOT/'stl'/f'{model}.stl') for model in models],
            ], check=True, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        print(f'Sliced {folder/name}-a2l-petg.3mf', flush=True)


if __name__ == '__main__':
    main()
