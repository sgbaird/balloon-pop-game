"""Illustrative paraxial flashlight rays; all dimensions are in millimetres.

Run with Python 3, NumPy and Matplotlib. No measured lens prescription is assumed.
"""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SHAPES = ("Uncovered", "Circle", "Square", "Triangle", "Cross")


def aperture(points, shape, width):
    x, y = points.T
    h = width / 2
    if shape == "Uncovered":
        return np.ones(len(x), dtype=bool)
    if shape == "Circle":
        return x*x + y*y <= h*h
    if shape == "Square":
        return (abs(x) <= h) & (abs(y) <= h)
    if shape == "Triangle":
        # Isosceles triangle: base y=-h, apex y=h, total width=width.
        return (y >= -h) & (y <= h) & (abs(x) <= (h-y)/2)
    if shape == "Cross":
        return ((abs(x) <= h) & (abs(y) <= width/5)) | (
            (abs(y) <= h) & (abs(x) <= width/5))
    raise ValueError(shape)


def propagate(source, pupil, distance, focal, travel):
    slope = (pupil-source)/distance - pupil/focal
    return pupil + travel*slope


def smooth(hist):
    # A one-bin Gaussian reduces Monte Carlo noise; not an optical blur model.
    kernel = np.exp(-np.arange(-3, 4)**2/2)
    kernel /= kernel.sum()
    for axis in (0, 1):
        hist = np.apply_along_axis(lambda a: np.convolve(a, kernel, "same"), axis, hist)
    return hist


def check(source, pupil, focal, wall, diameter, width):
    focused = focal*wall/(wall-focal)
    image = propagate(source, pupil, focused, focal, wall)
    np.testing.assert_allclose(image, -wall/focused*source, atol=1e-9)
    np.testing.assert_allclose(
        propagate(source, pupil, focal, focal, wall),
        pupil-wall/focal*source, atol=1e-9)
    if width <= diameter/np.sqrt(2):
        # For these contained apertures, geometric area predicts passed rays.
        areas = (np.pi*diameter**2/4, np.pi*width**2/4,
                 width**2, width**2/2, 0.64*width**2)
        for shape, area in zip(SHAPES, areas):
            measured = aperture(pupil, shape, width).mean()
            expected = area/areas[0]
            assert abs(measured-expected) < 0.008, (shape, measured, expected)
    print("PASS: finite-wall focus, collimation, and contained-aperture area checks")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--focal-mm", type=float, default=30)
    p.add_argument("--wall-mm", type=float, default=3000)
    p.add_argument("--led-mm", type=float, default=3)
    p.add_argument("--lens-mm", type=float, default=32)
    p.add_argument("--opening-mm", type=float, default=20)
    p.add_argument("--mask-gap-mm", type=float, default=0)
    p.add_argument("--rays", type=int, default=1_200_000)
    p.add_argument("--output", type=Path, default=Path(__file__).parent)
    args = p.parse_args()
    if not (args.wall_mm > args.focal_mm > 0 and args.led_mm > 0
            and args.lens_mm > 0 and args.opening_mm > 0 and args.rays >= 100_000
            and 0 <= args.mask_gap_mm < args.wall_mm):
        p.error("require positive dimensions, wall > focal, 0 <= gap < wall, rays >= 100000")
    rng = np.random.default_rng(5)
    source = rng.uniform(-args.led_mm/2, args.led_mm/2, (args.rays, 2))
    radius = args.lens_mm/2*np.sqrt(rng.random(args.rays))
    angle = rng.uniform(0, 2*np.pi, args.rays)
    pupil = np.column_stack((radius*np.cos(angle), radius*np.sin(angle)))
    f, wall = args.focal_mm, args.wall_mm
    check(source, pupil, f, wall, args.lens_mm, args.opening_mm)
    distances = (f*wall/(wall-f), f*26/30, f*18/30)
    labels = ("LED focused on wall", "Partly retracted", "Retracted / flood")
    fig, axes = plt.subplots(3, 5, figsize=(12, 8))
    records = []
    for row, (distance, label) in enumerate(zip(distances, labels)):
        image = propagate(source, pupil, distance, f, wall)
        mask_plane = propagate(source, pupil, distance, f, args.mask_gap_mm)
        a = 1+wall*(1/distance-1/f)
        extent = (abs(a)*args.lens_mm/2 + wall/distance*args.led_mm/2)*1.12
        images = []
        for shape in SHAPES:
            keep = aperture(mask_plane, shape, args.opening_mm)
            hist, _, _ = np.histogram2d(*image[keep].T, bins=180,
                                      range=((-extent, extent), (-extent, extent)))
            images.append(smooth(hist))
            records.append(dict(setting=label, led_lens_mm=distance, shape=shape,
                                transmitted_fraction=keep.mean(),
                                pupil_coefficient=a,
                                led_blur_width_mm=wall/distance*args.led_mm))
        vmax = images[0].max()
        for col, (shape, hist) in enumerate(zip(SHAPES, images)):
            ax = axes[row, col]
            ax.imshow(hist.T, origin="lower", cmap="inferno", vmin=0, vmax=vmax,
                      extent=(-extent, extent, -extent, extent))
            fraction = records[-5+col]["transmitted_fraction"]
            ax.set_title(f"{shape}: {fraction:.0%} rays", fontsize=10)
            ticks = [-round(extent*.7), 0, round(extent*.7)]
            ax.set_xticks(ticks)
            ax.set_yticks(ticks)
            ax.tick_params(labelsize=7)
            if col == 0:
                ax.set_ylabel(f"{label}\nd = {distance:.2f} mm\nWall y (mm)", fontsize=9)
            if row == 2:
                ax.set_xlabel("Wall x (mm)", fontsize=9)
    fig.suptitle("Front covers: near spot focus the LED image survives; flood reveals the opening\n"
                 f"ILLUSTRATIVE, NOT MEASURED: f={f:g} mm, LED={args.led_mm:g} mm square, "
                 f"lens={args.lens_mm:g} mm, wall={wall/1000:g} m\n"
                 f"Openings={args.opening_mm:g} mm, mask gap={args.mask_gap_mm:g} mm; "
                 "linear brightness shared within each row; row scales differ", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .91))
    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output/"front-mask-comparison.png", dpi=150)
    plt.close(fig)
    with (args.output/"results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    for label, distance in zip(labels, distances):
        a = 1+wall*(1/distance-1/f)
        print(f"{label}: d={distance:.4f} mm; A={a:.4f}; "
              f"LED blur={wall/distance*args.led_mm:.1f} mm; "
              f"opening scale={abs(a)*args.opening_mm:.1f} mm (gap=0)")


if __name__ == "__main__":
    main()
