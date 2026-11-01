"""Make a fit-check instruction sheet from the committed STL meshes.

Run: python cad/airhug02/preview_fit_check.py
Requires trimesh, scipy, matplotlib and Pillow. Does not change print files.
"""
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image, ImageDraw, ImageFont
import trimesh

ROOT = Path(__file__).resolve().parent
BG = "#f4f7fa"
INK = "#172b40"
BLUE = "#57a8bd"


def font(size, bold=False):
    return ImageFont.truetype(
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)


def render(mesh, color):
    fig = plt.figure(figsize=(3, 2.3), dpi=100, facecolor=BG)
    ax = fig.add_subplot(projection="3d", computed_zorder=False)
    ax.add_collection3d(Poly3DCollection(mesh.triangles, facecolors=color,
                                       shade=True,
                                       lightsource=matplotlib.colors.LightSource(120, 45)))
    center = mesh.bounds.mean(axis=0)
    radius = max(mesh.extents) * 0.55
    ax.set(xlim=(center[0]-radius, center[0]+radius),
           ylim=(center[1]-radius, center[1]+radius),
           zlim=(center[2]-radius, center[2]+radius))
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=42, azim=-65)
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def main():
    sheet = Image.new("RGB", (1200, 1100), BG)
    draw = ImageDraw.Draw(sheet)
    draw.text((32, 20), "AIRHUG 02: use the fit-check pieces", fill=INK, font=font(32, True))
    draw.text((32, 65), "Let prints cool. Remove brims, supports and loose strands before checking.",
              fill=INK, font=font(21))
    parts = sorted(trimesh.load(ROOT / "stl/coupon.stl").split(),
                   key=lambda mesh: mesh.bounds.mean(axis=0)[1], reverse=True)
    # Width gauge is the only component centred above Y=30; distinguish the
    # remaining ring and depth gauge by X, independent of STL component order.
    width = parts[0]
    ring, depth = sorted(parts[1:], key=lambda mesh: mesh.bounds.mean(axis=0)[0])
    meshes = [width, depth, ring, trimesh.load(ROOT / "stl/screw.stl")]
    labels = ["A  Long width gauge", "B  Small depth gauge", "C  Threaded ring", "D  Reusable screw"]
    for i, (mesh, label) in enumerate(zip(meshes, labels)):
        sheet.paste(render(mesh, BLUE if i < 3 else "#e6aa51"), (i*300, 105))
        draw.text((i*300+16, 335), label, fill=INK, font=font(20, True))
    draw.text((32, 375), "Actual STL shapes; each shown at its own scale. Blue = gauges, gold = screw.",
              fill=INK, font=font(19))
    cards = [
        ("1  Width: offer A across the widest part of the housing",
         ["Put the two end walls outside the camera's left and right ends.",
          "The clear span is 70.6 mm for a nominal 70 mm housing.",
          "Check the widest outline, not just the narrower rounded lower edge.",
          "PASS: a little play, no bending or force. It need not sit on the base."]),
        ("2  Depth: offer B across the main body's front and back",
         ["At an accessible spot, put the two walls either side of the main body.",
          "The clear gap is 25.6 mm for a nominal 25 mm body depth.",
          "Keep the projecting privacy cover, hinge, clip and cable out of the gap.",
          "PASS: light slip fit. If those features prevent access, measure with calipers."]),
        ("3  Thread: turn D's narrow tip into C by hand",
         ["Hold the ring square to the shaft; turn clockwise viewed from the knob.",
          "Run the ring along several turns of thread, then back it off.",
          "PASS: smooth finger turning without tools, jamming or cross-threading.",
          "Keep the screw for the full mount; the three blue pieces are only gauges."]),
    ]
    for i, (title, lines) in enumerate(cards):
        y = 420 + i*195
        draw.rounded_rectangle((24, y, 1176, y+180), radius=12, fill="white")
        draw.text((42, y+12), title, fill=INK, font=font(24, True))
        for j, line in enumerate(lines):
            draw.text((42, y+50+j*29), line, fill=INK, font=font(21))
    draw.text((32, 1022), "If tight: stop, note which piece binds and measure the camera / printed opening.",
              fill=INK, font=font(21, True))
    draw.text((32, 1057), "Prototype: these checks do not validate height, cover motion, ledge grip or holding force.",
              fill=INK, font=font(20))
    output = ROOT / "previews/fit-check-guide.png"
    sheet.save(output)
    print(f"Saved {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
