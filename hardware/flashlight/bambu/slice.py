"""Slice each printable flashlight part with the saved A1 mini / Generic PLA presets.

Run under xvfb-run with --studio pointing to the extracted AppImage's AppRun.
The README describes the runner's thumbnail-rendering limitation.
Uses only the Python standard library; never connects to a printer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(archive, name):
    """Check actual exported settings, toolpaths, layer count and plate metadata."""
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None, archive
        config = json.loads(z.read('Metadata/project_settings.config'))
        for key, expected in {
            'printer_model': 'Bambu Lab A1 mini',
            'printer_settings_id': 'Bambu Lab A1 mini 0.4 nozzle',
            'nozzle_diameter': ['0.4'],
            'filament_type': ['PLA'],
            'filament_settings_id': ['Generic PLA @BBL A1M'],
            'curr_bed_type': 'Textured PEI Plate',
            'layer_height': '0.2',
            'initial_layer_print_height': '0.2',
            'wall_loops': '4',
            'brim_type': 'no_brim',
            'enable_support': '0',
        }.items():
            assert config[key] == expected, (name, key, config[key])
        assert config['printable_area'] == ['0x0', '180x0', '180x180', '0x180']
        data = z.read('Metadata/plate_1.gcode')
        assert z.read('Metadata/plate_1.gcode.md5').decode().strip() == hashlib.md5(data).hexdigest().upper()
        gcode = data.decode()
        assert '; BambuStudio 02.08.02.61' in gcode
        assert ';===== machine: A1 mini' in gcode
        layers = [float(v) for v in re.findall(r'^; Z_HEIGHT: ([\d.]+)', gcode, re.M)]
        assert layers and abs(layers[0] - .2) < .0001
        assert all(abs(b - a - .2) < .0001 for a, b in zip(layers, layers[1:]))
        expected_layers = 1 if name == 'loose_diffuser_disk' else 40 if name.startswith('fit_') else 71 if name.endswith('_filled') else 76
        assert len(layers) == expected_layers, (name, len(layers), expected_layers)
        # Filled covers have infill on their optical face, then only sleeve walls.
        if name.endswith('_filled') or name == 'loose_diffuser_disk':
            chunks = re.split(r'^; Z_HEIGHT: [\d.]+', gcode, flags=re.M)[1:]
            assert '; FEATURE: Bottom surface' in chunks[0], name
            assert all('; FEATURE: Bottom surface' not in s and '; FEATURE: Internal solid infill' not in s for s in chunks[1:]), name
        info = ET.fromstring(z.read('Metadata/slice_info.config'))
        plate = info.find('plate')
        meta = {x.get('key'): x.get('value') for x in plate.findall('metadata')}
        assert meta['printer_model_id'] == 'N1', meta
        assert meta['outside'] == 'false' and meta['support_used'] == 'false', meta
        warnings = [x.attrib for x in plate.findall('warning')]
        return {
            'file': archive.name,
            'sha256': sha256(archive),
            'layers': len(layers),
            'max_z_mm': layers[-1],
            'estimated_seconds': int(meta['prediction']),
            'filament_g': float(meta['weight']),
            'warnings': warnings,
            'thumbnail': 'Metadata/plate_1.png' in z.namelist(),
            'gcode_sha256': hashlib.sha256(data).hexdigest(),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', type=Path, help='Path to extracted Bambu Studio AppRun')
    parser.add_argument('--output', type=Path, default=ROOT / 'sliced')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if not args.verify_only and not args.studio:
        parser.error('--studio is required for slicing')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in (ROOT.parent / 'stl').glob('*.stl') if p.stem != 'flashlight_reference')
    assert len(sources) == 22
    results = {}
    with tempfile.TemporaryDirectory(prefix='flashlight-slice-') as tmp:
        for source in sources:
            archive = args.output / (source.stem + '.3mf')
            if not args.verify_only:
                work = Path(tmp) / source.stem
                work.mkdir()
                command = [
                    str(args.studio.resolve()), '--datadir', str(Path(tmp) / 'userdata'),
                    '--debug', '2', '--load-settings',
                    f'{ROOT / "profiles/machine.json"};{ROOT / "profiles/process.json"}',
                    '--load-filaments', str(ROOT / 'profiles/filament.json'),
                    '--orient', '0', '--arrange', '1', '--ensure-on-bed',
                    '--slice', '0', '--outputdir', str(work),
                    '--export-3mf', archive.name, str(source),
                ]
                run = subprocess.run(command, capture_output=True, text=True, timeout=300)
                if run.returncode:
                    raise RuntimeError(run.stdout + run.stderr)
                status = json.loads((work / 'result.json').read_text())
                assert status['return_code'] == 0, status
                (work / archive.name).replace(archive)
            results[source.stem] = {'source_sha256': sha256(source), **inspect(archive, source.stem)}
            print(f'{source.stem}: {results[source.stem]["layers"]} layers, verified', flush=True)
    report = {
        'studio_version': '02.08.02.61',
        'source_model_commit': '9131b0f',
        'profiles_sha256': {p.name: sha256(p) for p in sorted((ROOT / 'profiles').glob('*.json'))},
        'parts': results,
    }
    report_path = args.output / 'report.json'
    if args.verify_only:
        assert report == json.loads(report_path.read_text()), 'Saved report differs from artifacts'
    else:
        report_path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
