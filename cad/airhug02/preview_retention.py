"""Dimensioned front projection of the side-lip revision (not a force model)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import numpy as np

ROOT = Path(__file__).resolve().parent


def main():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout='constrained')
    ax = axes[0]
    w, h = 70, 17.5
    points = []
    for c, angles in [((w-h)/2, np.linspace(-np.pi/2, np.pi/2, 100)),
                      (-(w-h)/2, np.linspace(np.pi/2, 3*np.pi/2, 100))]:
        points.extend([[c+h/2*np.cos(a), h/2+h/2*np.sin(a)] for a in angles])
    ax.fill(*np.array(points).T, color='#454c55', label='Nominal housing')
    ax.add_patch(Circle((-26, h/2), 3, color='#7ac8ef'))
    for x in [-41, 31]:
        ax.add_patch(Rectangle((x, -1), 10, 11, color='#e3a337', alpha=.85))
    ax.plot([-41,41],[0,0],color='#268296',lw=4)
    ax.annotate('', xy=(-31,22), xytext=(31,22), arrowprops=dict(arrowstyle='<->'))
    ax.text(0,23,'62 mm central opening',ha='center')
    ax.text(0,-6,'Front projection: lips sit ahead of the cover',ha='center',fontsize=9)
    ax.set(xlim=(-46,46), ylim=(-8,29), aspect='equal', title='Taller lips only at the outer ends', xlabel='X (mm)', ylabel='Height above floor (mm)')
    ax = axes[1]
    # Compare effective geometric rise, rather than pretending the capsule is square.
    report = json.loads((ROOT/'evidence/retention.json').read_text())
    low, high = report['lift_to_clear_range_mm']
    nominal = 10-(h/2-np.sqrt((h/2)**2-(31-(w-h)/2)**2))
    ax.barh([0,1],[.6,nominal],color=['#7b8791','#e3a337'],height=.5)
    ax.plot([low,high],[1,1],color='#453019',lw=3,marker='|',markersize=15)
    ax.text(.85,0,'0.6 mm toe',va='center')
    ax.text(.3,1.45,f'Side lips: {low:.1f}–{high:.1f} mm across 27 size scenarios\nNominal housing: {nominal:.1f} mm',fontsize=10)
    ax.text(.3,-.65,'Open top: camera can still be lifted out.\nNo impact, friction or holding-force prediction.',fontsize=10)
    ax.set(yticks=[0,1],yticklabels=['Previous','Revised'],xlim=(0,11),ylim=(-.9,1.95),xlabel='Rise before forward crossing clears (mm)',title='Rounded ends reduce effective engagement')
    ax.grid(axis='x',alpha=.2)
    fig.suptitle('Side-lip revision · no extra parts · physical fit and retention untested',fontsize=13)
    fig.savefig(ROOT/'previews/side-lips.png',dpi=140)


if __name__ == '__main__':
    main()
