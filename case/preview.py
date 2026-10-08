"""Preview images for generate_case.py.

  <board>_preview.png          shaded 3D views (top shell, its underside, base tray, assembled)
  <board>_<side>_sections.png  horizontal cuts through the top shell and base, with the PCB,
                               keycaps and component keep-outs overlaid (for checking fit)
  <board>_<side>_template_1to1.svg  print at 100% and lay the PCB on it before ordering the case

Pure numpy + matplotlib (software z-buffer), so it runs headless without OpenGL.
"""
import math, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Patch
from matplotlib.lines import Line2D
from manifold3d import Manifold, CrossSection, FillRule
from shapely.geometry.polygon import orient

TOP_C, BASE_C, PCB_C = '#5b8bd0', '#e8954a', '#ecece4'
SW_C, CAP_C = '#8a8f96', '#2f3640'

# ------------------------------------------------------------------ geometry helpers
def _polys(g):
    if g is None or g.is_empty: return []
    if g.geom_type == 'Polygon': return [g]
    return [p for q in getattr(g, 'geoms', []) for p in _polys(q)]

def _path(rings):
    verts, codes = [], []
    for r in rings:
        r = np.asarray(r, float)
        if len(r) < 3: continue
        verts += r.tolist() + [r[0].tolist()]
        codes += [Path.MOVETO] + [Path.LINETO] * (len(r) - 1) + [Path.CLOSEPOLY]
    return Path(verts, codes) if verts else None

def _gpath(g):
    rings = []
    for p in _polys(g):
        p = orient(p, 1.0)          # matplotlib fills with the non-zero rule: holes must run CW
        rings.append(np.asarray(p.exterior.coords)[:-1])
        rings += [np.asarray(h.coords)[:-1] for h in p.interiors]
    return _path(rings)

def _draw(ax, path, **kw):
    if path is not None:
        ax.add_patch(PathPatch(path, **kw))

def _prism(g, z0, z1):
    rings = []
    for p in _polys(g):
        rings.append(np.asarray(p.exterior.coords)[:-1])
        rings += [np.asarray(h.coords)[:-1] for h in p.interiors]
    return CrossSection(rings, FillRule.EvenOdd).extrude(z1 - z0).translate([0, 0, z0]) if rings else Manifold()

def _place(m, fp, z):
    return m.rotate([0, 0, -fp['rot']]).translate([fp['x'], fp['y'], z])

# ------------------------------------------------------------------ software renderer
def _mesh(m, rgb):
    mesh = m.to_mesh()
    V = np.asarray(mesh.vert_properties)[:, :3].astype(float) * [1, -1, 1]   # KiCad y-down -> y-up
    F = np.asarray(mesh.tri_verts).astype(np.int64)[:, ::-1]                 # mirror flips winding
    return V, F, np.array(matplotlib.colors.to_rgb(rgb))

def render(objs, az=-60.0, el=35.0, width=1000, ss=2, bg=(1.0, 1.0, 1.0), light=(-0.35, 0.55, 0.76)):
    """Orthographic z-buffer render of [(V, F, rgb), ...] with flat shading and outlines.
    light is given in screen space (x right, y up, z towards the viewer)."""
    a, e_ = math.radians(az), math.radians(el)
    eye = np.array([math.cos(e_) * math.cos(a), math.cos(e_) * math.sin(a), math.sin(e_)])
    right = np.cross([0.0, 0.0, 1.0], eye); right /= np.linalg.norm(right)
    R = np.stack([right, np.cross(eye, right), eye])
    light = np.asarray(light, float); light /= np.linalg.norm(light)
    pts = np.vstack([V for V, _, _ in objs]) @ R.T
    lo, hi = pts[:, :2].min(0), pts[:, :2].max(0)
    pad = 0.03 * (hi - lo).max(); lo, hi = lo - pad, hi + pad
    W = width * ss; s = W / (hi[0] - lo[0])
    H = int(math.ceil((hi[1] - lo[1]) * s / ss)) * ss
    zbuf = np.full((H, W), -np.inf); fid = np.full((H, W), -1, np.int64)
    cols, nrms, oids = [], [], []
    base = 0
    for oi, (V, F, rgb) in enumerate(objs):
        C = V @ R.T
        n = np.cross(C[F[:, 1]] - C[F[:, 0]], C[F[:, 2]] - C[F[:, 0]])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        shade = 0.32 + 0.68 * np.clip(n @ light, 0, 1)
        cols.append(np.clip(rgb[None, :] * shade[:, None] + 0.08 * shade[:, None] ** 8, 0, 1))
        nrms.append(n); oids.append(np.full(len(F), oi))
        X = (C[:, 0] - lo[0]) * s; Y = (hi[1] - C[:, 1]) * s; Z = C[:, 2]
        tx, ty, tz = X[F], Y[F], Z[F]
        den = (ty[:, 1] - ty[:, 2]) * (tx[:, 0] - tx[:, 2]) + (tx[:, 2] - tx[:, 1]) * (ty[:, 0] - ty[:, 2])
        x0 = np.clip(np.floor(tx.min(1)).astype(int), 0, W - 1); x1 = np.clip(np.ceil(tx.max(1)).astype(int), 0, W - 1)
        y0 = np.clip(np.floor(ty.min(1)).astype(int), 0, H - 1); y1 = np.clip(np.ceil(ty.max(1)).astype(int), 0, H - 1)
        for k in np.nonzero((n[:, 2] > 1e-6) & (np.abs(den) > 1e-12))[0]:     # front faces only
            xs = np.arange(x0[k], x1[k] + 1) + 0.5; ys = np.arange(y0[k], y1[k] + 1)[:, None] + 0.5
            (ax_, bx, cx), (ay, by, cy) = tx[k], ty[k]
            w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den[k]
            w1 = ((cy - ay) * (xs - cx) + (ax_ - cx) * (ys - cy)) / den[k]
            w2 = 1.0 - w0 - w1
            inside = (w0 >= -1e-7) & (w1 >= -1e-7) & (w2 >= -1e-7)
            z = w0 * tz[k, 0] + w1 * tz[k, 1] + w2 * tz[k, 2]
            zb = zbuf[y0[k]:y1[k] + 1, x0[k]:x1[k] + 1]; fb = fid[y0[k]:y1[k] + 1, x0[k]:x1[k] + 1]
            upd = inside & (z > zb)
            zb[upd] = z[upd]; fb[upd] = base + k
        base += len(F)
    cols, nrms, oids = np.vstack(cols), np.vstack(nrms), np.concatenate(oids)
    hit = fid >= 0
    img = np.empty((H, W, 3)); img[:] = bg
    img[hit] = cols[fid[hit]]
    # outlines: silhouettes, depth jumps, creases and part boundaries
    N = np.zeros((H, W, 3)); N[hit] = nrms[fid[hit]]
    O = np.full((H, W), -1); O[hit] = oids[fid[hit]]
    Zc = np.where(hit, zbuf, -1e6)
    edge = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a_ = (slice(0, H - dy), slice(0, W - dx)); b_ = (slice(dy, H), slice(dx, W))
        both = hit[a_] & hit[b_]
        e = (O[a_] != O[b_]) | (both & ((np.abs(Zc[a_] - Zc[b_]) > 0.5) | ((N[a_] * N[b_]).sum(-1) < 0.85)))
        edge[a_] |= e
    img[edge] = img[edge] * 0.35
    return img.reshape(H // ss, ss, W // ss, ss, 3).mean((1, 3))

# ------------------------------------------------------------------ figures
def _sections(h, path, board, P):
    zb = h.zb
    levels = [(h.top, 0.35, 'top shell, z=+0.35 mm (choc clip reliefs)', TOP_C),
              (h.top, 1.2, 'top shell, z=+1.2 mm (switch plate)', TOP_C),
              (h.top, 4.0, 'top shell, z=+4.0 mm (controller hood)', TOP_C),
              (h.base, -0.5, 'base, z=-0.5 mm (wall rim beside the PCB)', BASE_C),
              (h.base, -2.6, 'base, z=-2.6 mm (pillars, bosses, socket clearance)', BASE_C),
              (h.base, zb + 0.8, f'base, z={zb + 0.8:+.1f} mm (floor: nut pockets)', BASE_C)]
    minx, miny, maxx, maxy = h.outer.bounds
    view = h.outer.buffer(2.5)
    fig, axs = plt.subplots(2, 3, figsize=(19, 12), layout='constrained')
    for ax, (m, z, title, col) in zip(axs.flat, levels):
        _draw(ax, _path(m.slice(z).to_polygons()), fc=col, ec='k', lw=0.4, alpha=0.85)
        if m is h.base:
            _draw(ax, _gpath(h.under.intersection(h.pcb2d)), fc='#9b59b6', ec='none', alpha=0.25)
        else:
            _draw(ax, _gpath(h.keycaps), fill=False, ec='0.55', lw=0.5, ls=':')
        _draw(ax, _gpath(h.pcb2d), fill=False, ec='#1e8449', lw=0.9, ls='--')
        for q in h.parts:
            _draw(ax, _gpath(q['poly'].intersection(view)), fill=False, ec='#c0392b', lw=0.8)
        for (x, y, d) in h.mounts:
            ax.plot([x], [y], '+', color='k', ms=7, mew=1)
        ax.set_xlim(minx - 3, maxx + 3); ax.set_ylim(maxy + 3, miny - 3)   # KiCad y points down
        ax.set_aspect('equal'); ax.set_title(title, fontsize=10); ax.tick_params(labelsize=7)
    handles = [Patch(fc=TOP_C, ec='k', label='top shell material'), Patch(fc=BASE_C, ec='k', label='base material'),
               Line2D([], [], color='#1e8449', ls='--', label='PCB outline'),
               Line2D([], [], color='#c0392b', label='controller / switch / jack keep-outs'),
               Patch(fc='#9b59b6', alpha=0.25, label='hotswap sockets & parts under the PCB'),
               Line2D([], [], color='0.55', ls=':', label='keycaps (+clearance)'),
               Line2D([], [], marker='+', color='k', ls='', label='M2 screw')]
    fig.legend(handles=handles, loc='outside lower center', ncol=7, fontsize=9, frameon=False)
    fig.suptitle(f'{board} - {h.side} half - cross-sections seen from above (mm, KiCad coordinates)', fontsize=13)
    fig.savefig(path, dpi=90); plt.close(fig)

def _keycaps_and_switches(h, P):
    sw = [_place(CrossSection.square([P['flange'], P['flange']], center=True).extrude(5.5 - P['slab_t']), f, P['slab_t'])
          for f in h.switches]
    caps = [_place(CrossSection.square(list(P['keycap']), center=True).extrude(3.0, scale_top=(0.9, 0.88)), f, 5.1)
            for f in h.switches]
    return sw, caps

def _overview(halves, path, board, P):
    h = next((x for x in halves if x.side == 'left'), halves[0])
    panels = [('Top shell', [_mesh(h.top, TOP_C)], -60, 38, None),
              ('Top shell from below (clip reliefs, controller hood)', [_mesh(h.top, TOP_C)], -60, -38, (-0.35, -0.55, 0.76)),
              ('Base tray (screw bosses, PCB support pillars)', [_mesh(h.base, BASE_C)], -60, 38, None)]
    asm = []
    for x in halves:
        # the PCB panel has the halves swapped (left half at the right); lay them out as on a desk
        b = x.outer.bounds
        dx = (-20 - b[2]) if x.side == 'left' else (20 - b[0])
        sw, caps = _keycaps_and_switches(x, P)
        parts = [(x.base, BASE_C), (_prism(x.pcb2d, -P['pcb_t'], 0), PCB_C), (x.top, TOP_C)]
        parts += [(m, SW_C) for m in sw] + [(m, CAP_C) for m in caps]
        asm += [_mesh(m.translate([dx, 0, 0]), c) for m, c in parts]
    panels.append(('Assembled with PCB, switches and keycaps', asm, -75, 35, None))
    fig, axs = plt.subplots(2, 2, figsize=(18, 12.5), layout='constrained')
    for ax, (title, objs, az, el, light) in zip(axs.flat, panels):
        kw = dict(light=light) if light else {}
        ax.imshow(render(objs, az=az, el=el, width=1100, **kw)); ax.set_title(title, fontsize=12); ax.axis('off')
    fig.suptitle(f'{board}: {h.side} half' + (', and both halves assembled' if len(halves) > 1 else ''), fontsize=14)
    fig.savefig(path, dpi=80); plt.close(fig)

def _template(h, path, board, P):
    """1:1 drawing (top view, switches facing you) to check the real PCB before ordering the case."""
    m = 10.0
    minx, miny, maxx, maxy = h.outer.bounds
    W, H = maxx - minx + 2 * m, maxy - miny + 2 * m + 22
    tr = lambda x, y: (x - minx + m, y - miny + m + 14)
    def d(g):
        out = []
        for p in _polys(g):
            for ring in [p.exterior, *p.interiors]:
                out.append('M' + ' L'.join('%.3f,%.3f' % tr(*c) for c in ring.coords) + ' Z')
        return ' '.join(out)
    el = [f'<path d="{d(h.outer)}" fill="none" stroke="#999" stroke-width="0.3" stroke-dasharray="1.5,1"/>',
          f'<path d="{d(h.hood_out)}" fill="none" stroke="#5b8bd0" stroke-width="0.3" stroke-dasharray="1,1"/>',
          f'<path d="{d(h.cutouts)}" fill="none" stroke="#bbb" stroke-width="0.2"/>',
          f'<path d="{d(h.pcb2d)}" fill="none" stroke="#000" stroke-width="0.25"/>']
    for (x, y, dd) in h.mounts:
        cx, cy = tr(x, y)
        el.append(f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{max(dd, 2.2) / 2:.3f}" fill="none" stroke="#c0392b" stroke-width="0.25"/>')
        el.append(f'<path d="M{cx - 3:.3f},{cy:.3f} H{cx + 3:.3f} M{cx:.3f},{cy - 3:.3f} V{cy + 3:.3f}" stroke="#c0392b" stroke-width="0.15"/>')
    bx, by = m, m + 4
    el.append(f'<path d="M{bx},{by} h50 M{bx},{by - 1.5} v3 ' + ' '.join(f'M{bx + 10 * i},{by - 1} v2' for i in range(1, 5))
              + f' M{bx + 50},{by - 1.5} v3" stroke="#000" stroke-width="0.3"/>')
    el.append(f'<text x="{bx + 53}" y="{by + 1}" font-family="sans-serif" font-size="2.4">50 mm: print at 100% / actual size, then check this bar</text>')
    for i, line in enumerate([f'{board}, {h.side} half, seen from the switch side. Lay the PCB on it before ordering the case.',
                              'Black = PCB edge, red = screw holes, grey dashed = case outline, blue dashed = controller hood.']):
        el.append(f'<text x="{m}" y="{H - 7 + 3.5 * i:.2f}" font-family="sans-serif" font-size="2.4">{line}</text>')
    with open(path, 'w') as fh:
        fh.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}mm" height="{H:.2f}mm" viewBox="0 0 {W:.3f} {H:.3f}">\n'
                 + '\n'.join(el) + '\n</svg>\n')

def render_all(halves, out, board, P):
    files = []
    for h in halves:
        p = os.path.join(out, f'{board}_{h.side}_sections.png'); _sections(h, p, board, P); files.append(p)
        p = os.path.join(out, f'{board}_{h.side}_template_1to1.svg'); _template(h, p, board, P); files.append(p)
    p = os.path.join(out, f'{board}_preview.png'); _overview(halves, p, board, P); files.append(p)
    for f in files:
        print('  wrote', os.path.basename(f))
    return files
