"""Check delivered mesh topology, printer bounds, thread clearance and slice settings.
Requires numpy trimesh manifold3d shapely mapbox-earcut. Run after build.py.
"""
import hashlib
import itertools
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
    clamp=meshes['clamp'].copy();clamp.apply_translation([0,0,-19])
    clamp.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]))
    assert clamp.bounds[0,0]>=-41.0001,('left jamb clearance',clamp.bounds[0,0])
    screw=meshes['screw'].copy();screw.apply_translation([0,24,-41])
    clash=trimesh.boolean.intersection([clamp,screw],engine='manifold')
    assert abs(clash.volume)<0.01,('thread interference mm^3',clash.volume)
    # Advance and rotate together at the thread's 4 mm pitch. Include screw
    # positions for 25 mm and 10 mm ledges with the supplied 5 mm pad.
    thread_checks=[]
    for advance in np.linspace(-2.6,12.4,16):
        moving=meshes['screw'].copy()
        moving.apply_transform(trimesh.transformations.rotation_matrix(advance*np.pi/2,[0,0,1]))
        moving.apply_translation([0,24,-41+advance])
        overlap=abs(trimesh.boolean.intersection([clamp,moving],engine='manifold').volume)
        assert overlap<0.01,('advancing screw interference',advance,overlap)
        thread_checks.append(dict(advance_mm=float(advance),interference_mm3=float(overlap)))
    # Seat the pad's socket roof against the tip for a 20 mm example ledge.
    pad=meshes['pad'].copy()
    pad.apply_transform(trimesh.transformations.rotation_matrix(np.pi,[1,0,0]))
    pad.apply_translation([0,24,10])
    seated=meshes['screw'].copy()
    seated.apply_transform(trimesh.transformations.rotation_matrix(2.4*np.pi/2,[0,0,1]))
    seated.apply_translation([0,24,-38.6])
    pad_clash=abs(trimesh.boolean.intersection([pad,seated],engine='manifold').volume)
    assert pad_clash<0.01,('seated pad interference',pad_clash)
    assert abs(pad.bounds[1,2]-10)<1e-5
    assert abs(seated.bounds[1,2]-7.4)<1e-5
    # Camera envelope intersects only where holder fit would be impossible.
    camera=trimesh.load(ROOT/'stl/camera.stl');camera.apply_translation([0,-1.5,78.75])
    camera_clash=0.
    for piece in camera.split():
        if piece.is_volume:
            camera_clash+=abs(trimesh.boolean.intersection([clamp,piece],engine='manifold').volume)
    assert camera_clash<0.1,('camera interference mm^3',camera_clash)
    # Independent envelope sweep, not just subtraction of the nominal model.
    # Capsules are constructed independently of the OpenSCAD camera export.
    def body(w,h,d):
        radius=h/2
        outline=[]
        for centre,angles in [((w-h)/2,np.linspace(-np.pi/2,np.pi/2,65)),
                              (-(w-h)/2,np.linspace(np.pi/2,3*np.pi/2,65))]:
            outline.extend([[centre+radius*np.cos(a),radius*np.sin(a)] for a in angles])
        from shapely.geometry import Polygon
        mesh=trimesh.creation.extrude_polygon(Polygon(outline),d,engine='earcut')
        # extrusion local Z -> global Y, polygon Y -> global Z
        mesh.apply_transform(np.array([[1,0,0,0],[0,0,1,-14],[0,1,0,70+h/2],[0,0,0,1]]))
        assert mesh.is_volume
        return mesh
    def volume(a,b):
        return abs(trimesh.boolean.intersection([a,b],engine='manifold').volume)
    sweep=[]
    key=meshes['key'].copy()
    key.apply_translation([0,0,-6])
    key.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[0,1,0]))
    for w,h,d in itertools.product([66,70,74],[16,18,20],[23,25,28]):
        housing=body(w,h,d)
        interference=volume(clamp,housing)
        assert interference<0.01,(w,h,d,interference)
        # Find a non-intersecting seated keeper position, with 0.1 mm margin.
        # This demonstrates adjustment travel, not friction or retaining force.
        low,high=55.,92.
        for _ in range(12):
            z=(low+high)/2
            keeper=key.copy();keeper.apply_translation([31,18,z])
            if volume(housing,keeper)<0.001:
                high=z
            else:
                low=z
        seat=round(high+0.1,2)
        keeper=key.copy();keeper.apply_translation([31,18,seat])
        assert volume(clamp,keeper)<0.01,(w,h,d,'keeper/clamp',seat,volume(clamp,keeper))
        assert volume(housing,keeper)<0.01,(w,h,d,'keeper/body')
        assert 55<seat<85,(w,h,d,seat)
        sweep.append(dict(width=w,height=h,depth=d,interference_mm3=interference,keeper_tip_z=seat))
    clip=trimesh.creation.box([44,55,27]);clip.apply_translation([0,25,55.5])
    clip_clash=volume(clamp,clip)
    assert clip_clash<0.01,('clip keepout',clip_clash)
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
            assert cfg['bridge_no_support']=='1'
            gcode=z.read('Metadata/plate_1.gcode').decode()
            assert 'machine: A1 mini' in gcode
            assert 'M140 S65' in gcode
            assert '; layer num/total_layer_count: 1/' in gcode
        assert len(result['sliced_plates'])==1,('expected one plate',name)
        p=result['sliced_plates'][0]
        expected=['clamp.stl','screw.stl','pad.stl','key.stl','key.stl'] if name=='mount' else ['coupon.stl','screw.stl']
        assert sorted(o['name'] for o in p['objects'])==sorted(expected)
        for obj in p['objects']:
            b=obj['bbox']
            assert b['x']>=0 and b['y']>=0 and b['z']>=-0.001
            assert b['x']+b['width']<=180 and b['y']+b['depth']<=180
            assert b['z']+b['height']<=180

        reports[name]={'grams':round(p['filaments'][0]['total_used_g'],2),
                       'estimated_seconds':round(p['total_predication']),
                       'slicer_warning':p.get('warning_message','')}
    report={'watertight_print_meshes':True,'thread_interference_mm3':float(clash.volume),
            'camera_interference_mm3':camera_clash,'slices':reports,
            'housing_scenarios':sweep,'clip_keepout_interference_mm3':clip_clash,
            'thread_travel_scenarios':thread_checks,'seated_pad_interference_mm3':pad_clash,
            'not_validated':['physical fit','print quality','PLA creep','clamp holding force','camera view on site']}
    report['artifact_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(list((ROOT/'stl').glob('*.stl'))+list((ROOT/'slicer').glob('*/*.3mf')))}
    (ROOT/'evidence/validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
