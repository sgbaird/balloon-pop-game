"""Create video-pose previews; requires OpenSCAD, xvfb-run, Pillow."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'previews'

def render(job):
    name, transform, camera, part = job
    call = 'reference(show_lens=false)' if part == 'reference' else part + '()'
    source = f'use <{ROOT / "flashlight.scad"}>\n{transform} {call};\n'
    with tempfile.NamedTemporaryFile(suffix='.scad', mode='w') as f:
        f.write(source)
        f.flush()
        subprocess.run(['xvfb-run', '-a', 'openscad', '-o', str(OUT / f'{name}.png'),
                        '--imgsize=1000,650', '--colorscheme=Tomorrow',
                        *([] if name == 'reference-front' else ['--viewall', '--autocenter']),
                        f'--camera={camera}', f.name],
                       check=True, capture_output=True)

def main():
    OUT.mkdir(exist_ok=True)
    jobs = [
        ('reference-side', 'rotate([0,90,0]) rotate([0,0,180])', '0,0,0,0,0,0,250', 'reference'),
        ('reference-front', 'rotate([180,0,0])', '0,0,0,0,0,0,125', 'reference'),
        ('reference-oblique', '', '0,0,0,145,0,35,250', 'reference'),
        ('apertures', '', '0,0,0,25,0,0,300', 'preview_lineup'),
    ]
    # A use directive imports modules only; their file-level parameters retain defaults.
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(render, jobs))
    turns = [('turn-%02d' % i, f'rotate([0,0,{i*30}])',
              '0,0,0,130,0,25,250', 'reference') for i in range(12)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(render, turns))
    frames = [Image.open(OUT / f'{name}.png').convert('RGB') for name, *_ in turns]
    frames[0].save(OUT / 'turntable.gif', save_all=True, append_images=frames[1:],
                   duration=180, loop=0)
    for name, *_ in turns:
        (OUT / f'{name}.png').unlink()

if __name__ == '__main__':
    main()
