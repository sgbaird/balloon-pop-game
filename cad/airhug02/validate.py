"""Check delivered mesh topology, printer bounds, thread clearance and slice settings.
Requires numpy trimesh manifold3d. Run after build.py.
"""
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parent

def main():
    meshes={}
    for name,count in [('clamp',1),('screw',1),('pad',1),('key',1),('coupon',3)]:
        m=trimesh.load(ROOT/'stl'/f'{name}.stl');meshes[name]=m
        assert m.is_watertight and m.is_volume,name
        assert len(m.split())==count,(name,len(m.split()))
        assert min(m.bounds[0,2:])>=-1e-4,name
        assert np.all(m.extents<=180),name
    # Undo the clamp's print orientation, then place screw at illustrated phase.
    clamp=meshes['clamp'].copy();clamp.apply_translation([0,0,-40])
    clamp.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,[0,1,0]))
    screw=meshes['screw'].copy();screw.apply_translation([0,24,-41])
    clash=trimesh.boolean.intersection([clamp,screw],engine='manifold')
    assert abs(clash.volume)<0.01,('thread interference mm^3',clash.volume)
    # Camera envelope intersects only where holder fit would be impossible.
    camera=trimesh.load(ROOT/'stl/camera.stl');camera.apply_translation([0,0,83])
    camera_clash=0.
    for piece in camera.split():
        if piece.is_volume:
            camera_clash+=abs(trimesh.boolean.intersection([clamp,piece],engine='manifold').volume)
    assert camera_clash<0.1,('camera interference mm^3',camera_clash)
    reports={}
    for name in ['mount','fit-check']:
        folder=ROOT/'slicer'/name
        result=json.loads((folder/'result.json').read_text());assert result['return_code']==0
        assert not result['sliced_plates'][0].get('warning_message'),result
        with zipfile.ZipFile(folder/f'{name}-a1mini-pla.3mf') as z:
            cfg=json.loads(z.read('Metadata/project_settings.config'))
            assert cfg['printer_model']=='Bambu Lab A1 mini'
            assert cfg['printable_area']==['0x0','180x0','180x180','0x180']
            assert cfg['filament_type']==['PLA']
            assert cfg['nozzle_diameter']==['0.4']
            assert cfg['enable_support']=='1'
            gcode=z.read('Metadata/plate_1.gcode').decode()
            assert 'machine: A1 mini' in gcode
            assert 'M140 S65' in gcode
            assert '; layer num/total_layer_count: 1/' in gcode
        p=result['sliced_plates'][0]
        reports[name]={'grams':round(p['filaments'][0]['total_used_g'],2),
                       'estimated_seconds':round(p['total_predication']),
                       'slicer_warning':p.get('warning_message','')}
    report={'watertight_print_meshes':True,'thread_interference_mm3':float(clash.volume),
            'camera_interference_mm3':camera_clash,'slices':reports,
            'not_validated':['physical fit','print quality','PLA creep','clamp holding force','camera view on site']}
    report['artifact_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(list((ROOT/'stl').glob('*.stl'))+list((ROOT/'slicer').glob('*/*.3mf')))}
    (ROOT/'evidence/validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
