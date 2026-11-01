"""Plot actual sliced extrusion moves; omits custom start/end G-code and travel."""
from pathlib import Path
import argparse
import json
import re
import zipfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=ROOT/'slicer/mount/mount-a1mini-pla.3mf')
    parser.add_argument('--output',type=Path,default=ROOT/'previews/toolpaths.png')
    args=parser.parse_args()
    with zipfile.ZipFile(args.project) as archive:
        gcode=archive.read('Metadata/plate_1.gcode').decode()
        config=json.loads(archive.read('Metadata/project_settings.config'))
    area=[list(map(float,p.split('x'))) for p in config['printable_area']]
    width=max(p[0] for p in area);depth=max(p[1] for p in area)
    material=config['filament_type'][0]
    segments=[];supports=[];first=[];layer=0;role='';x=y=0.;printing=False
    for line in gcode.splitlines():
        if line=='; CHANGE_LAYER':
            layer+=1;printing=True
        if line.startswith('; layer num/total_layer_count:'):
            layer=int(line.split(':')[1].split('/')[0]);printing=True
        if line.startswith('; FEATURE:'):role=line.split(':',1)[1].strip()
        if line.startswith('G1 ') or line.startswith('G0 '):
            values={k:float(v) for k,v in re.findall(r'([XYE])(-?\d*\.?\d+)',line.split(';')[0])}
            nx=values.get('X',x);ny=values.get('Y',y)
            if printing and role!='Custom' and values.get('E',0)>0 and (nx!=x or ny!=y):
                seg=[(x,y),(nx,ny)]
                (supports if 'Support' in role else segments).append(seg)
                if layer==1:first.append(seg)
            x,y=nx,ny
    assert segments and first, 'No extrusion paths or first layer found'
    fig,axes=plt.subplots(1,2,figsize=(10,5),layout='constrained')
    for ax in axes:
        ax.set(xlim=(0,width),ylim=(0,depth),aspect='equal',xlabel='X (mm)',ylabel='Y (mm)')
        ax.grid(alpha=.15)
    axes[0].add_collection(LineCollection(segments,colors='#266e88',linewidths=.15,alpha=.3))
    axes[0].add_collection(LineCollection(supports,colors='#dc9b36',linewidths=.2,alpha=.6))
    axes[0].set_title(f'All layers: model blue, {material} supports gold')
    axes[1].add_collection(LineCollection(first,colors='#266e88',linewidths=.4))
    axes[1].set_title('First layer, including brims')
    fig.suptitle(f"Bambu Studio toolpaths · {config['printer_model']} · {config['nozzle_diameter'][0]} mm · Generic {material}")
    fig.savefig(args.output,dpi=140)

if __name__=='__main__':main()
