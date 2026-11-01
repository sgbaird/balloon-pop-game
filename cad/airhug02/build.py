"""Export meshes, flatten bundled Bambu presets (including G-code includes), slice.
Usage: python build.py /tmp/squashfs-root/AppRun
Install OpenSCAD, Bambu Studio Linux AppImage dependencies and Xvfb first.
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
PARTS=['clamp','screw','pad','key','coupon','camera']

def run(args):
    subprocess.run([str(a) for a in args],check=True,cwd=ROOT)

def presets(app, output=None, names=None):
    output = ROOT/'slicer' if output is None else Path(output)
    output.mkdir(parents=True, exist_ok=True)
    base=app.parent/'resources/profiles/BBL'
    index={}
    for p in base.rglob('*.json'):
        try:
            j=json.loads(p.read_text());index[j.get('name',p.stem)]=p
        except ValueError:
            pass
    def resolve(name):
        j=json.loads(index[name].read_text());r={}
        if j.get('inherits'):r.update(resolve(j['inherits']))
        for inc in j.get('include',[]):r.update(resolve(inc))
        r.update(j);r.pop('inherits',None);r.pop('include',None)
        return r
    names=names or {'machine':'Bambu Lab A1 mini 0.4 nozzle',
           'process':'0.20mm Standard @BBL A1M','filament':'Generic PLA @BBL A1M'}
    for kind,name in names.items():
        j=resolve(name)
        if kind=='machine': j['printer_settings_id']=name
        if kind=='process':
            j.update(wall_loops='5',sparse_infill_density='30%',sparse_infill_pattern='gyroid',
                     top_shell_layers='5',bottom_shell_layers='5',enable_support='1',
                     bridge_no_support='1',support_type='normal(auto)',support_on_build_plate_only='0',
                     brim_type='outer_only',brim_width='5',curr_bed_type='Textured PEI Plate',
                     print_settings_id='AIRHUG clamp '+names['process'])
        (output/f'{kind}.json').write_text(json.dumps(j,indent=2)+'\n')

def main():
    app=Path(sys.argv[1]).resolve()
    for part in PARTS:
        run(['openscad','-o',f'stl/{part}.stl','-D',f'part="{part}"','mount.scad'])
    presets(app)
    for name,models in [('mount',['clamp','screw','pad','key','key']),('fit-check',['coupon','screw'])]:
        out=ROOT/'slicer'/name;out.mkdir(exist_ok=True)
        run(['xvfb-run','-a',app,'--load-settings',f'{ROOT}/slicer/machine.json;{ROOT}/slicer/process.json',
             '--load-filaments',ROOT/'slicer/filament.json','--orient','0','--arrange','1',
             '--slice','0','--export-3mf',f'{name}-a1mini-pla.3mf','--outputdir',out,
             *[ROOT/'stl'/f'{p}.stl' for p in models]])
    for name,part in [('assembly','assembly'),('camera','camera')]:
        run(['xvfb-run','-a','openscad','-o',f'previews/{name}.png','--imgsize=1000,800',
             '--viewall','--autocenter','--projection=o','--colorscheme=Tomorrow',
             '-D',f'part="{part}"','mount.scad'])

if __name__=='__main__': main()
