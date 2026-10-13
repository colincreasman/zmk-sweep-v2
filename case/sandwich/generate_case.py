#!/usr/bin/env python3
"""Sandwich case for the wireless Ferris Sweep Bling LP: the Totemist look on the enclosed case.

Everything from the enclosed case (../enclosed) stays: the 2.2 mm plate sits on the PCB and the Choc
clips snap under it, the same base tray, hex nuts, M2x8 screws, USB-C slot, power-switch slot and
reset hole. What changes is the top shell: its rim rises to just under the keycap tops and every key
sits in a well, like ErgoMech's Totemist and GEIST's TOTEM. The nice!nano and battery live under the
rim's roof, so the enclosed case's raised hood is gone.

Writes to stl/ for each half: <board>_<side>_top.stl and <board>_<side>_base.stl, plus
<board>_report.json and preview pictures.

Usage:  python generate_case.py [--out DIR] [--sides left right] [--rim MM] [--no-preview]
Requires: pip install manifold3d shapely trimesh numpy matplotlib rtree
"""
import argparse
import importlib.util
import json
import math
import os
import sys

import numpy as np
from shapely.ops import unary_union

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sandwich as sw  # noqa: E402

_spec = importlib.util.spec_from_file_location('enclosed_case', os.path.join(HERE, '..', 'enclosed', 'generate_case.py'))
enc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enc)

BOARD = 'sweep-bling-lp'
RIM_MIN = 2.5        # narrowest rim around the main keys; the outline grows where the PCB is tighter
NANO_GAP = 0.45      # keycap-to-wall gap along the nice!nano, which sits 0.46 mm from the inner column
CORNER_R = 2.0       # outside corners of the (grown) outline are rounded at least this much


def keys_of(h):
    out = []
    for f in h.switches:
        a = math.radians(f['rot'])
        out.append(sw.Key((f['x'], f['y']), (math.cos(a), -math.sin(a)), thumb=round(f['rot']) % 180 != 0,
                          name=f['ref']))
    return out


def plate_cuts(h):
    """The enclosed case's plate details: 14 mm cut-outs, clip reliefs, screw holes, countersinks."""
    p = enc.P
    t = p['slab_t']
    w0, w1, ry = p['relief_w0'], p['relief_w1'], p['cut'] + 0.1
    rel = (enc.CrossSection.square([w0, ry], center=True).extrude(p['relief_z'], scale_top=(w1 / w0, 1.0))
           + enc.CrossSection.square([w0, ry], center=True).extrude(1.0).translate([0, 0, -1.0])
           + enc.CrossSection.square([w1, ry], center=True).extrude(p['ledge_z'] - p['relief_z'] + 0.05)
           .translate([0, 0, p['relief_z'] - 0.05]))
    neg = [enc.prism(h.cutouts, -1, t + 1)] + [enc.place(rel, f) for f in h.switches]
    for (x, y, d) in h.mounts:
        r0, r1 = p['screw_d'] / 2, p['csk_d'] / 2
        neg.append(enc.Manifold.cylinder(t + 2, r0, circular_segments=48).translate([x, y, -1]))
        neg.append(enc.Manifold.cylinder(r1 - r0 + 0.001, r0, r1, circular_segments=48).translate([x, y, t - (r1 - r0)]))
    return sw.union(neg)


def build_half(prof, side, rim):
    h0 = enc.Half(prof, side).build()                 # the enclosed case, for its outline and comparisons
    keys = keys_of(h0)
    W, H = sw.MBK['size']
    c = sw.TOTEM['cap_clear']
    main = unary_union([k.rect(W + 2 * c, H + 2 * c) for k in keys if not k.thumb])
    thumbs = unary_union([k.rect(W, H) for k in keys if k.thumb])
    grown = unary_union([h0.outer, main.buffer(RIM_MIN, join_style=2), thumbs.buffer(1.0, join_style=2)])
    outline = sw.smooth(grown, CORNER_R)

    h = enc.Half(prof, side).build(outer=outline)    # same base as the enclosed case, on the grown outline
    keepouts = [(q['poly'], q['z'][1]) for q in h.parts if q['kind'] == 'hood']
    cuts = [enc.prism(q['poly'], -1, 60) for q in h.parts if q['kind'] == 'hole']
    cuts += [enc.prism(q['poly'], *q['z']) for q in h.parts if q['kind'] == 'slot']
    screws = [dict(c=(x, y), bore=enc.P['csk_d'] + 0.3) for (x, y, d) in h.mounts]
    s = sw.Sandwich(outline, 0.0, keys, (0.0, 1.0), plate_cuts(h), screws=screws, keepouts=keepouts, cuts=cuts,
                    rim=rim, tight_clear=NANO_GAP)
    s.build()
    top = sw.trim_thin(s.solid, enc.P['min_feature'])
    s.info['trimmed_mm3'] = round(s.solid.volume() - top.volume(), 2)
    return h0, h, s, keys, top


def check(h, s, keys, top):
    parts = sw.union([sw.prism(p, 0.01, z) for p, z in s.keepouts])
    against = {'PCB': enc.prism(h.pcb2d, -enc.P['pcb_t'], 0), 'switches': sw.switches(keys, 0.0),
               'keycaps, full travel': sw.keycap_sweep(keys, 0.0), 'nice!nano, battery, TRRS, reset': parts,
               'USB-C slot, reset hole': sw.union(s.cuts)}
    r_top = sw.report('top', top, against)
    r_top['closed_pockets'] = sw.closed_pockets(top, s.outline, 0.0, s.rim_h)
    r_top['ok'] = r_top['ok'] and not r_top['closed_pockets']
    ko = h.keepouts()
    r_base = sw.report('base', h.base, {k: v for k, v in ko.items() if k != 'keycaps_pressed'})
    return r_top, r_base


def pictures(out, halves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    shell, base, cap, sw_col, pcb_col = (0.16, 0.17, 0.19), (0.30, 0.32, 0.36), (0.80, 0.80, 0.82), (0.85, 0.65, 0.25), (0.15, 0.45, 0.25)
    h0, h, s, keys, top = halves[0]
    flip = lambda m: m.mirror([0, 1, 0])         # KiCad's y-down -> real world for 3D views
    caps = sw.keycaps(keys, 0.0)
    pcb = enc.prism(h.pcb2d, -enc.P['pcb_t'], 0)
    fig, ax = plt.subplots(2, 2, figsize=(17, 12.5), dpi=90)
    sw.render(ax[0, 0], [(flip(h.base), base), (flip(top), shell), (flip(caps), cap)], sw.look(28, -100),
              f'{h.side.capitalize()} half assembled, MBK keycaps')
    sw.render(ax[0, 1], [(flip(h.base), base), (flip(pcb), pcb_col), (flip(sw.switches(keys, 0.0)), sw_col),
                         (flip(top).translate([0, 0, 22]), shell)], sw.look(35, -60), 'Top shell lifted off')
    H, (x0, x1, y0, y1) = sw.heightmap(flip(top))
    im = ax[1, 0].imshow(H, origin='lower', extent=[x0, x1, y0, y1], cmap='viridis')
    fig.colorbar(im, ax=ax[1, 0], shrink=0.8, label='height above the PCB (mm)')
    ax[1, 0].set_title('Top shell from above: rim (yellow), thumb shelf and well floors (purple)', fontsize=10)
    ax[1, 0].set_aspect('equal')
    ax[1, 0].axis('off')
    sw.render(ax[1, 1], [(flip(top), shell)], sw.look(-50, -110), 'Top shell from below: hollow rim, open to the PCB')
    fig.tight_layout()
    fig.savefig(os.path.join(out, f'{BOARD}_preview.png'))
    plt.close(fig)

    # side profiles: enclosed (Forager-style) case vs sandwich case
    main = [k for k in keys if not k.thumb]
    xm = np.median([k.c[0] for k in main])
    col = sorted(main, key=lambda k: abs(k.c[0] - xm))[:3]
    home = sorted(col, key=lambda k: k.c[1])[1]
    thumb = max([k for k in keys if k.thumb], key=lambda k: abs(k.c[0] - home.c[0]))
    fig, ax = plt.subplots(2, 2, figsize=(16, 8.5), dpi=100)
    style = lambda colr: dict(facecolor=colr, edgecolor='k', lw=0.5)
    for j, (name, tp, bs) in enumerate((('Enclosed (Forager-style)', h0.top, h0.base), ('Sandwich (Totemist-style)', top, h.base))):
        parts = [(bs, style('#59606b')), (pcb, style('#2a7a3e')), (tp, style('#2a2b30'))]
        sw.profile(ax[0, j], home, 0.0, parts, f'{name}: middle-finger column, you are on the right', (0.0, 1.0), span=34)
        sw.profile(ax[1, j], thumb, 0.0, parts, f'{name}: thumb key, you are on the right', (0.0, 1.0), span=22)
    for a in ax.flat:
        a.set_ylim(-7.5, 12.5)
    for a in ax[:, 1]:
        a.axhline(s.info['rim_z'], color='#d62728', lw=0.8, ls=':')
        a.text(a.get_xlim()[0] + 0.5, s.info['rim_z'] - 0.9, f'sandwich rim {s.info["rim_z"]:.2f} mm above PCB',
               color='#d62728', fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(out, f'{BOARD}_profile.png'))
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(HERE, 'stl'))
    ap.add_argument('--sides', nargs='+', default=['left', 'right'])
    ap.add_argument('--rim', type=float, default=sw.TOTEM['rim'],
                    help=f'rim height above the PCB top (default {sw.TOTEM["rim"]}, like the TOTEM/Totemist; '
                         f'{sw.MBK["top"]} = level with MBK keycap tops)')
    ap.add_argument('--no-preview', action='store_true')
    a = ap.parse_args()
    prof = enc.PROFILES[BOARD]
    os.makedirs(a.out, exist_ok=True)
    report = dict(board=BOARD, rim_above_pcb=a.rim, mbk_top_above_pcb=sw.MBK['top'], halves={})
    halves, ok = [], True
    for side in a.sides:
        print(f'[{side}] building ...')
        h0, h, s, keys, top = build_half(prof, side, a.rim)
        r_top, r_base = check(h, s, keys, top)
        for r in (r_top, r_base):
            clash = {k: v for k, v in r['clash_mm3'].items() if v > 1e-3}
            print(f"  {r['part']:4s} pieces={r['pieces']} vol={r['volume_cm3']}cm3 size={r['size_mm']} "
                  f"gaps={r['gap_mm']} clash={clash} -> {'OK' if r['ok'] else 'CHECK'}")
            ok &= r['ok']
        stem = os.path.join(a.out, f'{BOARD}_{side}')
        r_top['stl_ok'] = enc.export(top, stem + '_top.stl')
        r_base['stl_ok'] = enc.export(h.base, stem + '_base.stl')
        ok &= r_top['stl_ok'] and r_base['stl_ok']
        h.top = top                 # optional switch film: where this top shell's plate sits on the PCB
        h.film()
        fi = h.film_info
        print(f"  film {fi['size_mm'][0]} x {fi['size_mm'][1]} mm, {fi['pieces']} piece(s), {fi['clearance_mm']} mm "
              f"from every top-shell opening and the PCB edge -> {'OK' if fi['ok'] else 'CHECK'}")
        report['halves'][side] = dict(top=r_top, base=r_base, shell=s.info, mounts=h.boss_info, film=fi,
                                      outline_grown_mm2=round(h.outer.area - h0.outer.area, 1))
        halves.append((h0, h, s, keys, top))
    for f in enc.write_film([q[1] for q in halves], a.out, BOARD):
        print('  wrote', os.path.basename(f))
    with open(os.path.join(a.out, f'{BOARD}_report.json'), 'w') as fh:
        json.dump(report, fh, indent=1, default=str)
    if not a.no_preview:
        pictures(a.out, halves)
    print('done ->', a.out, '' if ok else '  (some checks FAILED: see above)')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
