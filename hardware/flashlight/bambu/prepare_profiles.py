"""Flatten Bambu Studio's bundled preset inheritance/includes for its CLI.

Usage: python prepare_profiles.py /path/to/squashfs-root
Uses only the Python standard library. Run against the pinned release in README.
"""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def resolve(profiles, kind, name, ancestors=()):
    if name in ancestors:
        raise ValueError(f'Preset inheritance cycle: {ancestors}, {name}')
    data = json.loads((profiles / kind / (name + '.json')).read_text())
    ancestors = (*ancestors, name)
    base = resolve(profiles, kind, data['inherits'], ancestors) if data.get('inherits') else {}
    for include in data.get('include', []):
        base.update(resolve(profiles, kind, include, ancestors))
    base.update(data)
    base.pop('inherits', None)
    base.pop('include', None)
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('appdir', type=Path)
    args = parser.parse_args()
    profiles = args.appdir / 'resources/profiles/BBL'
    output = ROOT / 'profiles'
    output.mkdir(exist_ok=True)
    for kind, name in [
        ('machine', 'Bambu Lab A1 mini 0.4 nozzle'),
        ('process', '0.20mm Standard @BBL A1M'),
        ('filament', 'Generic PLA @BBL A1M'),
    ]:
        data = resolve(profiles, kind, name)
        if kind == 'process':
            data.update(initial_layer_print_height='0.2', layer_height='0.2',
                        wall_loops='4', brim_type='no_brim', enable_support='0',
                        curr_bed_type='Textured PEI Plate')
        if kind == 'machine':
            data['default_filament_profile'] = ['Generic PLA @BBL A1M']
        (output / (kind + '.json')).write_text(json.dumps(data, indent=2) + '\n')
    model = profiles / 'machine/Bambu Lab A1 mini.json'
    shutil.copyfile(model, output / 'machine_model.json')
    # This release's CLI searches machine_full rather than machine for model_id.
    destination = profiles / 'machine_full'
    destination.mkdir(exist_ok=True)
    shutil.copyfile(model, destination / model.name)


if __name__ == '__main__':
    main()
