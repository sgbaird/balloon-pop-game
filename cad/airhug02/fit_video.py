"""Reproduce hand-landmark silhouette fits from the issue video (not calibration).
Usage: python fit_video.py /path/to/video.mp4
Requires numpy scipy opencv-python-headless pillow. Source remains outside repo.
"""
import json
from pathlib import Path
import sys
import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
# Pixel coordinates in autorotated portrait frames, 1080 x 1920.
LANDMARKS = {
    36: [[414,879],[425,849],[453,839],[478,851],[525,922],
         [645,1107],[674,1140],[677,1164],[662,1184],[638,1198],
         [612,1189],[575,1147],[519,1060],[470,981],[430,921],[411,894]],
    45: [[510,941],[513,1050],[520,1200],[520,1267],[532,1294],
         [555,1310],[585,1315],[613,1304],[634,1282],[642,1251],
         [637,1157],[632,1010]],
}

def outline(height):
    a=np.linspace(-np.pi/2,np.pi/2,100)
    half=(65-height)/2; r=height/2
    x=np.r_[half+r*np.cos(a),np.linspace(half,-half,150),
            -half-r*np.cos(a),np.linspace(-half,half,150)]
    y=np.r_[r*np.sin(a),np.full(150,r),-r*np.sin(a),np.full(150,-r)]
    return np.c_[x,y,np.zeros(len(x))]

def project(points, pose, focal):
    p=Rotation.from_rotvec(pose[:3]).apply(points)+pose[3:]
    return p[:,:2]/p[:,2,None]*focal+[540,960]

def fit(focal, fixed_height=None):
    # Width is a tape-derived scale assumption, not solved from monocular video.
    initial=[17]
    for angle,cx,cy,scale in [(57,544,1018,6.3),(89,574,1070,7.5)]:
        initial.extend([0.2,0.1,np.deg2rad(angle),(cx-540)/scale,(cy-960)/scale,focal/scale])
    initial=np.array(initial)
    def residual(v):
        h=v[0] if fixed_height is None else fixed_height
        r=[]
        for i,obs in enumerate(LANDMARKS.values()):
            q=project(outline(h),v[1+6*i:7+6*i],focal)
            dist,_=cKDTree(q).query(obs)
            r.extend(dist)
        # weak pose prior prevents unconstrained grazing views in occluded frame
        r.extend(v[[1,2,7,8]]*2)
        return r
    result=least_squares(residual,initial,max_nfev=600,loss='soft_l1',f_scale=3,
                         bounds=([12]+[-np.inf]*12,[23]+[np.inf]*12))
    errors=[]
    for i,obs in enumerate(LANDMARKS.values()):
        q=project(outline(result.x[0] if fixed_height is None else fixed_height),result.x[1+6*i:7+6*i],focal)
        d,_=cKDTree(q).query(obs);errors.extend(d)
    return result.x,float(np.sqrt(np.mean(np.square(errors))))

def main():
    cap=cv2.VideoCapture(sys.argv[1]); panels=[];fits=[]
    for focal in [900,1400,2200]:
        v,rms=fit(focal)
        fits.append({'focal_px_assumed':focal,'height_mm_fit':round(v[0],2),
                     'landmark_rms_px':round(rms,2),
                     'poses':[{'rotvec':v[1+6*i:4+6*i].tolist(),'translation_mm':v[4+6*i:7+6*i].tolist()} for i in range(2)]})
    v,rms=fit(1400);_,before=fit(1400,19)
    for i,(second,obs) in enumerate(LANDMARKS.items()):
        cap.set(cv2.CAP_PROP_POS_MSEC,second*1000);ok,frame=cap.read()
        if not ok: raise RuntimeError(f'Missing frame {second}')
        im=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));draw=ImageDraw.Draw(im)
        pose=v[1+6*i:7+6*i]
        for depth,color in [(0,'#00ffff'),(10,'#ffaa33')]:
            pts=outline(v[0]);pts[:,2]=depth
            q=project(pts,pose,1400);draw.line([tuple(p) for p in np.vstack([q,q[0]])],fill=color,width=3)
        for x,y in obs: draw.ellipse((x-4,y-4,x+4,y+4),fill='#ff2870')
        im=im.crop((340,750,800,1400));im.thumbnail((460,650));panels.append(im)
    out=Image.new('RGB',(920,730),'#202630');d=ImageDraw.Draw(out)
    for i,p in enumerate(panels):out.paste(p,(i*460,50))
    d.text((18,12),'36s: rear                         45s: closed front cover',fill='white')
    d.text((18,705),'Cyan: fitted CAD face; orange: 10mm depth; pink: manual silhouette landmarks',fill='white')
    out.save(ROOT/'previews/video-fit.png')
    report={'method':'Manual visible capsule silhouette landmarks; width fixed from tape; square pixels; centred principal point; zero distortion assumed.',
        'frame_size':[1080,1920],'K_assumed':[[1400,0,540],[0,1400,960],[0,0,1]],
        'baseline_height_mm':19,'baseline_refit_rms_px':before,'sensitivity':fits,
        'limitations':'Focal length is NOT identified: equally plausible poses fit multiple focal lengths. Distances scale with focal prior. Not AIRHUG intrinsics; this is the recording phone. Width/depth and hidden hinge remain approximate. Manual landmarks and occlusion limit accuracy.'}
    (ROOT/'evidence/fit.json').write_text(json.dumps(report,indent=2)+'\n')
    (ROOT/'evidence/landmarks.json').write_text(json.dumps(LANDMARKS,indent=2)+'\n')
    print(json.dumps({'height':v[0],'rms':rms,'baseline':before,'sensitivity':[(x['focal_px_assumed'],x['height_mm_fit'],x['landmark_rms_px']) for x in fits]},indent=2))

if __name__=='__main__': main()
