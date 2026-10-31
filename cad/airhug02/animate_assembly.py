"""Render the existing CAD parts into a captioned assembly GIF.

Requires OpenSCAD, Xvfb and Pillow. Run from any working directory:
    python cad/airhug02/animate_assembly.py
No print meshes, slicer projects or CAD dimensions are changed.
"""
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("1 / 6   Insert the printed screw", "Turn upward through the bottom jaw."),
    ("2 / 6   Place the loose pressure pad", "Socket down, over the screw tip."),
    ("3 / 6   Slide onto the corner ledge", "Seat the spine at the lip and left stop at the jamb."),
    ("4 / 6   Tighten lightly by hand", "Keep at least two full turns engaged; check the grip."),
    ("5 / 6   Lower the camera into the saddles", "Original clip already folded; leave the cable free."),
    ("6 / 6   Insert both keeper wedges", "Thin tips down, caps forward. Seat gently."),
]


def font(size):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def main():
    frames, durations = [], []
    with tempfile.TemporaryDirectory(prefix="airhug-assembly-") as temp:
        # One X server for all frames. Fixed camera prevents framing changes.
        commands = []
        samples = [(step, i / 10) for step in range(6) for i in range(11)]
        for index, (step, fraction) in enumerate(samples):
            path = Path(temp) / f"{index:03}.png"
            commands.append([
                "openscad", "-o", str(path), "--imgsize=800,660",
                "--camera=0,0,25,68,0,65,600", "--projection=o",
                "--colorscheme=Tomorrow", "-D", f"t={step+fraction}",
                str(ROOT / "assembly_animation.scad"),
            ])
        # Pass argv as JSON to a child under Xvfb, avoiding shell interpolation.
        import json
        import sys
        subprocess.run([
            "xvfb-run", "-a", sys.executable, "-c",
            "import json,subprocess,sys; "
            "[subprocess.run(c,check=True,stdout=subprocess.DEVNULL,"
            "stderr=subprocess.DEVNULL) for c in json.load(sys.stdin)]",
        ], input=json.dumps(commands), text=True, check=True, cwd=ROOT)
        for index, (step, fraction) in enumerate(samples):
            with Image.open(Path(temp) / f"{index:03}.png") as rendered:
                frame = Image.new("RGB", (800,800), "#202630")
                frame.paste(rendered.convert("RGB"), (0,80))
            draw = ImageDraw.Draw(frame)
            title, detail = STEPS[step]
            draw.text((24,15), title, font=font(24), fill="white")
            draw.text((24,48), detail, font=font(17), fill="#d1d8e0")
            draw.rectangle((0,740,800,800), fill="#202630")
            draw.text((24,751), "CAD prototype demonstration - physical fit untested",
                      font=font(17), fill="#d1d8e0")
            draw.text((24,777), "Check cover, live view and saved calibration after installation.",
                      font=font(14), fill="#aebccc")
            frames.append(frame)
            durations.append(1600 if fraction == 1 else 90)
        output = ROOT / "previews/assembly.gif"
        frames[0].save(output, save_all=True, append_images=frames[1:],
                       duration=durations, loop=0, optimize=True, disposal=2)
        print(f"Saved {output.relative_to(ROOT)} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
