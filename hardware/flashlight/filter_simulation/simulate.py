"""First-order spot-mode filter study, not a measured Duracell lens prescription."""
import argparse
import csv
import itertools
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Educational three-band transmissions in R,G,B order; NOT product data or sRGB.
FILTERS = {
    'Unfiltered': (1., 1., 1.),
    'Blue': (.02, .08, .75),
    'Yellow': (.80, .80, .02),
    'Cyan': (.02, .80, .80),
    'Magenta': (.80, .02, .80),
}
STACKS = [('Unfiltered',), ('Blue',), ('Yellow',), ('Blue', 'Yellow'),
          ('Cyan', 'Yellow'), ('Cyan', 'Magenta'), ('Magenta', 'Yellow'),
          ('Cyan', 'Magenta', 'Yellow')]


def transmission(stack):
    return np.prod([FILTERS[name] for name in stack], axis=0)


def sample(rng, count, led, diameter):
    source = rng.uniform(-led/2, led/2, (count, 2))
    theta = rng.uniform(0, 2*np.pi, count)
    radius = diameter/2 * np.sqrt(rng.random(count))
    pupil = np.column_stack((radius*np.cos(theta), radius*np.sin(theta)))
    return source, pupil


def trace(source, pupil, spacing, focal, wall):
    slope = (pupil-source)/spacing - pupil/focal
    # Lambertian emitter to parallel pupil: cos(source)*cos(pupil)/r^2.
    weights = spacing**2 / (spacing**2 + ((pupil-source)**2).sum(axis=1))**2
    weights /= weights.sum()
    return pupil + wall*slope, weights


def radius90(points, weights):
    radius = np.linalg.norm(points, axis=1)
    order = np.argsort(radius)
    return np.interp(.9*weights.sum(), np.cumsum(weights[order]), radius[order])


def save_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def verify(source, pupil, f, wall):
    focused = f*wall/(wall-f)
    image, _ = trace(source, pupil, focused, f, wall)
    np.testing.assert_allclose(image, -wall/focused*source, atol=1e-9)
    collimated, weights = trace(source, pupil, f, f, wall)
    np.testing.assert_allclose(collimated, pupil-wall/f*source, atol=1e-9)
    np.testing.assert_allclose(weights.sum(), 1)
    # A spatially uniform clear filter must preserve the normalized footprint.
    bins = np.linspace(-1000, 1000, 101)
    baseline = np.histogram(collimated[:, 0], bins=bins, weights=weights)[0]
    filtered = np.histogram(collimated[:, 0], bins=bins, weights=weights*.27)[0]
    np.testing.assert_allclose(filtered, baseline*.27, atol=1e-12)
    np.testing.assert_allclose(transmission(('Blue', 'Yellow')), [.016, .064, .015])
    np.testing.assert_allclose(transmission(('Cyan', 'Magenta', 'Yellow')), [.0128]*3)
    print('PASS: finite-wall imaging, collimation, energy normalization, clear-filter footprint, stack products')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video-spacing-mm', type=float, default=18)
    parser.add_argument('--extension-mm', type=float, default=24)
    parser.add_argument('--focal-mm', type=float, default=None,
                        help='default: video spacing + extension (collimated spot hypothesis)')
    parser.add_argument('--lens-mm', type=float, default=32)
    parser.add_argument('--led-mm', type=float, default=3)
    parser.add_argument('--wall-mm', type=float, default=3000)
    parser.add_argument('--filter-gap-mm', type=float, default=50)
    parser.add_argument('--scatter-fraction', type=float, default=.65)
    parser.add_argument('--scatter-sigma-deg', type=float, default=4)
    parser.add_argument('--rays', type=int, default=400000)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'results')
    args = parser.parse_args()
    d = args.video_spacing_mm + args.extension_mm
    f = args.focal_mm if args.focal_mm is not None else d
    dims = [args.video_spacing_mm, args.lens_mm, args.led_mm, args.wall_mm, f]
    if (not all(np.isfinite(x) and x > 0 for x in dims)
            or not np.isfinite(args.extension_mm) or args.extension_mm < 0
            or not 0 <= args.filter_gap_mm < args.wall_mm or args.wall_mm <= f
            or not 0 <= args.scatter_fraction <= 1
            or not 0 <= args.scatter_sigma_deg < 30 or args.rays < 10000):
        parser.error('require finite positive geometry, wall > focal, gap in [0, wall), '
                     'extension >= 0, scatter fraction in [0,1], sigma in [0,30), rays >= 10000')
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(5)
    source, pupil = sample(rng, args.rays, args.led_mm, args.lens_mm)
    verify(source, pupil, f, args.wall_mm)
    image, weights = trace(source, pupil, d, f, args.wall_mm)
    r90 = radius90(image, weights)
    # Thin scattering sheet: add independent Gaussian angular slopes after the lens.
    sigma = np.deg2rad(args.scatter_sigma_deg)
    offsets = rng.normal(0, sigma, image.shape) * (args.wall_mm-args.filter_gap_mm)
    scattered = image + offsets
    frac = args.scatter_fraction
    mixed_points = np.concatenate((image, scattered))
    mixed_weights = np.concatenate(((1-frac)*weights, frac*weights))
    np.testing.assert_allclose(mixed_weights.sum(), 1)
    np.testing.assert_allclose(image + offsets*0, image)
    diffuse_r90 = radius90(mixed_points, mixed_weights)
    core_mask = np.linalg.norm(image, axis=1) <= r90
    diffuse_core = float(mixed_weights[np.linalg.norm(mixed_points, axis=1) <= r90].sum())
    cases = [('Unfiltered', ('Unfiltered',), False), ('Clear blue', ('Blue',), False),
             ('Clear yellow', ('Yellow',), False), ('Scattering blue', ('Blue',), True)]
    extent = max(600., r90*1.5, diffuse_r90*1.3)
    histargs = dict(bins=180, range=((-extent, extent), (-extent, extent)))
    base = np.histogram2d(*image.T, weights=weights, **histargs)[0]
    diffuse = np.histogram2d(*mixed_points.T, weights=mixed_weights, **histargs)[0]
    fig, axes = plt.subplots(2, 4, figsize=(12, 6.8))
    rows = []
    for col, (name, stack, is_diffuse) in enumerate(cases):
        t = transmission(stack)
        power = float(t.mean())  # Equal incident energy in each illustrative band.
        hist = (diffuse if is_diffuse else base)*power
        axes[0, col].imshow(hist.T, origin='lower', cmap='inferno', vmin=0,
                            vmax=base.max(), extent=(-extent, extent, -extent, extent))
        axes[0, col].set_title(f'{name}\n{power:.1%} three-band power')
        axes[0, col].set_xlabel('Wall x (mm)')
        axes[0, col].set_ylabel('Wall y (mm)')
        # Radial encircled energy exposes halos without auto-normalizing the image.
        for pts, w, label in [(image, weights, 'Clear'),
                              (mixed_points, mixed_weights, 'Scattering')]:
            radii = np.linalg.norm(pts, axis=1)
            order = np.argsort(radii)
            axes[1, col].plot(radii[order][::500],
                              (np.cumsum(w[order])*power)[::500], label=label)
        axes[1, col].set(xlim=(0, extent), ylim=(0, 1), xlabel='Radius (mm)',
                         ylabel='Fraction of unfiltered power')
        axes[1, col].grid(alpha=.2)
        rows.append(dict(case=name, r90_mm=diffuse_r90 if is_diffuse else r90,
                         three_band_power_fraction=power,
                         fraction_within_unfiltered_r90=diffuse_core if is_diffuse else float(weights[core_mask].sum())))
    axes[1, 0].legend()
    fig.suptitle(f'Extended spot: d={d:g} mm = {args.video_spacing_mm:g} + {args.extension_mm:g} mm; '
                 f'f={f:g} mm; wall={args.wall_mm/1000:g} m\n'
                 'ASSUMED optics & filter properties; shared linear intensity; colors indicate intensity only', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .91))
    fig.savefig(out/'spot-filters.png', dpi=140)
    plt.close(fig)
    save_csv(out/'spot_metrics.csv', rows)

    stack_rows = []
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(STACKS))
    for index, stack in enumerate(STACKS):
        t = transmission(stack)
        stack_rows.append(dict(stack='+'.join(stack), red=t[0], green=t[1], blue=t[2],
                               equal_band_power_fraction=float(t.mean())))
    for band, color in enumerate(('tomato', 'seagreen', 'royalblue')):
        ax.bar(x+(band-1)*.24, [transmission(s)[band] for s in STACKS], .24,
               color=color, label=('Red band', 'Green band', 'Blue band')[band])
    ax.set_xticks(x, [' +\n'.join(s) for s in STACKS], fontsize=8)
    ax.set(ylabel='Band transmission', ylim=(0, 1.12),
           title='Illustrative filter stacking: multiply transmissions, keep spot geometry\n'
                 'Three bands, equal incident energy; no measured gel spectra or camera color model')
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(out/'filter-stacks.png', dpi=140)
    plt.close(fig)
    save_csv(out/'stack_metrics.csv', stack_rows)

    # Sensitivity ranges are hypotheses, not confidence intervals or measured bounds.
    sweep_rows = []
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for lens, led, focal, offset, wall in itertools.product(
            (28., 32., 36.), (2., 3., 4.), (32., 42., 52.), (-1., 0., 1.), (1000., 3000., 5000.)):
        spacing = focal+offset
        # Common random numbers; normalize by actual emitter/pupil sampling scales.
        pts, w = trace(source[:30000]*led/args.led_mm,
                       pupil[:30000]*lens/args.lens_mm, spacing, focal, wall)
        sweep_rows.append(dict(lens_mm=lens, led_mm=led, focal_mm=focal,
                               spot_spacing_mm=spacing, inferred_video_spacing_mm=spacing-args.extension_mm,
                               focus_offset_mm=offset, wall_mm=wall, r90_mm=radius90(pts, w)))
    for ax, wall in zip(axes, (3000., 5000.)):
        for offset, marker in zip((-1., 0., 1.), ('v', 'o', '^')):
            subset = [r for r in sweep_rows if r['wall_mm'] == wall and r['focus_offset_mm'] == offset]
            ax.scatter([r['focal_mm'] for r in subset], [r['r90_mm'] for r in subset],
                       s=16, marker=marker, alpha=.6, label=f'd - f = {offset:+g} mm')
        ax.set(xlabel='Assumed focal length (mm)', ylabel='Unfiltered r90 (mm)',
               title=f'Wall {wall/1000:g} m; LED 2/3/4 mm, pupil 28/32/36 mm')
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('Spot geometry uncertainty: 24 mm travel does not uniquely specify the lens', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, .92))
    fig.savefig(out/'geometry-sensitivity.png', dpi=140)
    plt.close(fig)
    save_csv(out/'geometry_sweep.csv', sweep_rows)
    config = vars(args).copy()
    config.update(output=out.name, focal_mm=f, spot_spacing_mm=d, seed=5,
                  bands='illustrative equal-energy R,G,B; not spectral or camera prediction',
                  filter_transmissions=FILTERS, sweep_sample_count=min(30000, args.rays))
    (out/'parameters.json').write_text(json.dumps(config, indent=2)+'\n')
    print(json.dumps(rows, indent=2))
    print(f'PASS: scatter energy conservation; wrote {len(sweep_rows)} sensitivity cases to {out}')


if __name__ == '__main__':
    main()
