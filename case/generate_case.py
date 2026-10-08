#!/usr/bin/env python3
"""Parametric enclosed two-piece case for a wireless Ferris Sweep (Kailh Choc v1 hotswap).

Reads the board's open-source KiCad PCB, then builds per half:
  * <board>_<side>_top.stl  - top shell: 2.2 mm switch plate that sits on the PCB
                              (Forager-style choc clip reliefs) + raised hood over
                              the controller/battery, countersunk M2 screw holes.
  * <board>_<side>_base.stl - bottom tray: floor, walls up to the PCB top, screw
                              bosses with M2 hex-nut pockets, PCB support pillars.
plus switch_fit_coupon.stl (cutout-size sample), preview PNGs, and cutting files for an
optional switch film (thin plastic sheet between the PCB and the top shell):
  * <board>_film_template_1to1.svg - print at 100%, lay the film on it and cut along the lines
  * <board>_film_cut.svg / .dxf     - the same outlines only, for a cutting machine

Usage:  python generate_case.py --board <profile> [--out DIR] [--no-preview]
Requires: pip install manifold3d shapely trimesh numpy matplotlib
"""
import argparse, json, math, os, re, sys
import numpy as np
from manifold3d import Manifold, CrossSection, FillRule, JoinType
from shapely.geometry import Polygon, MultiPolygon, MultiPoint, Point, LineString, box
from shapely.ops import unary_union, polygonize
import trimesh

sys.dont_write_bytecode = True   # importing preview.py shouldn't leave __pycache__ in the repo
HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------------------
# Global parameters (mm). z = 0 is the PCB top surface; the PCB occupies -pcb_t..0.
# --------------------------------------------------------------------------------------
P = dict(
    pcb_t=1.6,            # PCB thickness
    gap=0.4,              # PCB edge -> inner wall clearance
    wall=1.6,             # side wall thickness (case outline = PCB + gap + wall)
    slab_t=2.2,           # plate thickness = PCB top -> underside of choc flange
    edge_chamfer=0.6,     # top outer edge chamfer (stepped)
    cut=14.0,             # switch cutout (choc v1 lower housing is 13.8; PCB pegs locate the switch)
    relief_w0=15.8,       # clip relief width at the PCB (along the switch's peg axis)
    relief_w1=14.6,       # ... tapering to this at relief_z
    relief_z=0.66,
    ledge_z=0.70,         # clips catch under this ledge
    cav=3.0,              # air gap below the PCB (hotswap sockets hang 1.85 below it)
    floor=1.6,            # floor thickness
    seam_drop=0.2,        # base wall top sits this far below PCB top so screws clamp the PCB
    screw_d=2.4,          # M2 clearance
    csk_d=4.4,            # countersink diameter at the plate top (90 deg, M2 ISO 10642)
    nut_af=4.3,           # M2 hex nut pocket across flats (nut is 4.0)
    nut_depth=1.8,        # pocket depth from the bottom face (nut sits below the sockets)
    under_h=1.9,          # hotswap sockets / pin tails hang this far below the PCB
    boss_d=5.6,
    pillar_d=3.2,
    min_clear=0.3,        # clearance from bosses/pillars to underside parts
    keycap=(17.45, 16.45),  # MBK-style choc keycap footprint (local x, local y)
    keycap_clear=0.6,
    keycap_pressed_z=3.58,  # keycap skirt bottom when fully pressed
    flange=15.0,          # choc top housing / flange footprint
    flange_clear=0.25,    # hood -> top housing (static; keeps the hood's lip by the inner column ~1 mm)
    hood_wall=1.4,
    hood_roof=1.2,
    hood_clear=0.4,
    feet_d=0.0,           # >0 adds recesses for round bumpers (e.g. 8.2 for 8 mm feet)
    feet_depth=0.6,
    min_feature=0.8,      # walls/slivers thinner than this (in plan view) are trimmed away;
                          # print services reject or mangle walls under ~0.8 mm
    film_clear=0.3,       # switch film: gap to every opening of the top shell and to the PCB edge
    film_min=1.5,         # switch film: strips narrower than this are left out (fiddly, tear off)
)

# --------------------------------------------------------------------------------------
# Board profiles. Footprint-local boxes are in KiCad footprint coordinates (mm, y down,
# before rotation) and z relative to the PCB top. kinds:
#   hood   - tall part on top: covered by the raised hood (slab removed underneath)
#   pocket - low part on top: blind pocket in the plate underside (z1 = height)
#   hole   - opening through the plate (e.g. paper-clip access to reset)
#   slot   - cut through walls/hood/base (USB-C plug, power-switch lever)
#   below  - part under the PCB (keeps pillars/bosses away; deepens the floor if needed)
# --------------------------------------------------------------------------------------
PROFILES = {
    'sweep-bling-lp': dict(
        title='Ferris Sweep Bling LP (davidphilipbarr/Sweep), nice!nano face-down',
        pcb='pcb/sweepbling-lp.kicad_pcb',
        halves={'left': (130.302, 1e9), 'right': (-1e9, 130.302)},
        switch_fp=r'Choc', mount_fp=r'MountingHole',
        ignore_fp=r'mouse-bite|ferris_broom|Tenting|1pin_conn',
        parts=[
            # nice!nano v2 face-down on low-profile headers with a 301230 LiPo between the headers;
            # header pins reach z 5.5 (measured from keebmaker's 3D model of this exact build)
            dict(fp=r'ProMicro', kind='hood', box=(-9.2, -19.7, 9.2, 15.1), z=(0, 5.6)),
            # wire bay past the USB end for the battery-lead loop keebmaker leaves there
            dict(fp=r'ProMicro', kind='hood', box=(-9.2, -19.7 - 5.0, 9.2, -19.7), z=(0, 5.6)),
            # USB-C plug channel (receptacle hangs under the face-down nano, mouth at y 46.4)
            dict(fp=r'ProMicro', kind='slot', box=(-6.2, -60, 6.2, -18.0), z=(-1.9, 5.3)),
            # TRRS jack (may be absent on wireless builds - covered anyway) and reset button
            dict(fp=r'TRRS', kind='hood', auto='F.SilkS', margin=0.2, z=(0, 5.0)),
            dict(fp=r'B3U', kind='hood', auto='F.CrtYd', margin=0.0, z=(0, 1.7)),
            dict(fp=r'B3U', kind='hole', box=(-0.9, -0.9, 0.9, 0.9), z=(-1, 60)),   # paper-clip access
            # power slide switch on the underside; lever pokes past the top edge -> slot to reach it
            dict(fp=r'SPDT', kind='below', auto='B.Fab', margin=0.3, z=(-3.3, -1.6)),
            dict(fp=r'SPDT', kind='slot', box=(-2.6, 1.0, 2.6, 60), z=(-3.4, -1.4)),
        ],
    ),
}

# --------------------------------------------------------------------------------------
# Minimal KiCad (s-expression) reader
# --------------------------------------------------------------------------------------
_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')

def sparse(text):
    stack = [[]]
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop(); stack[-1].append(x)
        else:
            stack[-1].append(t[1:-1] if t[0] == '"' else t)
    return stack[0][0]

def find(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]

def find1(node, name):
    r = find(node, name); return r[0] if r else None

def _pt(n):
    return (float(n[1]), float(n[2]))

def arc3(p1, p2, p3, seg=0.25):
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-12:
        return [p1, p3]
    ux = ((x1*x1 + y1*y1) * (y2 - y3) + (x2*x2 + y2*y2) * (y3 - y1) + (x3*x3 + y3*y3) * (y1 - y2)) / d
    uy = ((x1*x1 + y1*y1) * (x3 - x2) + (x2*x2 + y2*y2) * (x1 - x3) + (x3*x3 + y3*y3) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    a1, a2, a3 = (math.atan2(y - uy, x - ux) for x, y in (p1, p2, p3))
    s13, s12 = (a3 - a1) % (2 * math.pi), (a2 - a1) % (2 * math.pi)
    sweep = s13 if s12 <= s13 else -(2 * math.pi - s13)
    n = max(4, int(abs(sweep) * r / seg))
    pts = [(ux + r * math.cos(a1 + sweep * i / n), uy + r * math.sin(a1 + sweep * i / n)) for i in range(n + 1)]
    pts[0], pts[-1] = p1, p3
    return pts

def arc_center(c, s, deg, seg=0.25):
    r = math.hypot(s[0] - c[0], s[1] - c[1]); a0 = math.atan2(s[1] - c[1], s[0] - c[0])
    sw = math.radians(deg); n = max(4, int(abs(sw) * r / seg))
    return [(c[0] + r * math.cos(a0 + sw * i / n), c[1] + r * math.sin(a0 + sw * i / n)) for i in range(n + 1)]

def circle_pts(c, r, n=72):
    return [(c[0] + r * math.cos(t), c[1] + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, n + 1)]

def graphic_polyline(g, tf=lambda p: p):
    kind = g[0][3:]
    if kind == 'line':
        pts = [_pt(find1(g, 'start')), _pt(find1(g, 'end'))]
    elif kind == 'arc':
        if find1(g, 'mid') is not None:
            pts = arc3(_pt(find1(g, 'start')), _pt(find1(g, 'mid')), _pt(find1(g, 'end')))
        else:
            pts = arc_center(_pt(find1(g, 'start')), _pt(find1(g, 'end')), float(find1(g, 'angle')[1]))
    elif kind == 'circle':
        c = _pt(find1(g, 'center')); e = _pt(find1(g, 'end'))
        pts = circle_pts(c, math.hypot(e[0] - c[0], e[1] - c[1]))
    elif kind == 'rect':
        (x1, y1), (x2, y2) = _pt(find1(g, 'start')), _pt(find1(g, 'end'))
        pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    elif kind == 'poly':
        pts = [(float(p[1]), float(p[2])) for p in find1(g, 'pts') if isinstance(p, list) and p[0] == 'xy']
        pts = pts + [pts[0]]
    else:
        return None
    return [tf(p) for p in pts]

def board_region(pcb):
    """PCB area from Edge.Cuts (outer outlines minus internal cut-outs)."""
    lines = []
    for g in pcb:
        if isinstance(g, list) and g and g[0].startswith('gr_'):
            lay = find1(g, 'layer')
            if lay and lay[1] == 'Edge.Cuts':
                pl = graphic_polyline(g)
                if pl:
                    lines.append(pl)
    for f in footprints(pcb):           # outlines drawn inside footprints
        for g in f['node']:
            if isinstance(g, list) and g and g[0].startswith('fp_'):
                lay = find1(g, 'layer')
                if lay and lay[1] == 'Edge.Cuts':
                    pl = graphic_polyline(g, lambda p, f=f: fp_to_board(f, *p))
                    if pl:
                        lines.append(pl)
    reps = []
    def snap(p):
        for q in reps:
            if math.hypot(p[0] - q[0], p[1] - q[1]) < 0.02:
                return q
        reps.append(p); return p
    segs = []
    for pl in lines:
        pl = list(pl); pl[0] = snap(pl[0]); pl[-1] = snap(pl[-1])
        segs.append(LineString(pl))
    faces = list(polygonize(unary_union(segs)))
    keep = []
    for f in faces:
        rp = f.representative_point()
        depth = sum(1 for g in faces if g is not f and Polygon(g.exterior).contains(rp))
        if depth % 2 == 0:
            keep.append(f)
    return unary_union(keep)

def footprints(pcb):
    out = []
    for f in find(pcb, 'footprint') + find(pcb, 'module'):
        at = find1(f, 'at'); x, y = float(at[1]), float(at[2])
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = '?'
        for t in find(f, 'fp_text'):
            if t[1] == 'reference': ref = t[2]
        for p in find(f, 'property'):
            if p[1] == 'Reference': ref = p[2]
        out.append(dict(lib=f[1], ref=ref, x=x, y=y, rot=rot, layer=find1(f, 'layer')[1], node=f))
    return out

def fp_to_board(fp, lx, ly):
    a = math.radians(fp['rot'])
    return (fp['x'] + lx * math.cos(a) + ly * math.sin(a), fp['y'] - lx * math.sin(a) + ly * math.cos(a))

def pads(fp):
    res = []
    for p in find(fp['node'], 'pad'):
        at = find1(p, 'at'); size = find1(p, 'size'); drill = find1(p, 'drill'); layers = find1(p, 'layers')
        dr = None
        if drill:
            vals = [float(v) for v in drill[1:] if not isinstance(v, list) and v != 'oval']
            dr = max(vals) if vals else None
        bx, by = fp_to_board(fp, float(at[1]), float(at[2]))
        res.append(dict(x=bx, y=by, type=p[2], size=(float(size[1]), float(size[2])) if size else (0, 0),
                        drill=dr, layers=layers[1:] if layers else []))
    return res

def fp_local_bbox(fp, layer):
    pts = []
    for g in fp['node']:
        if isinstance(g, list) and g and g[0].startswith('fp_'):
            lay = find1(g, 'layer')
            if lay and lay[1] == layer:
                pl = graphic_polyline(g)
                if pl: pts += pl
    if not pts:
        raise ValueError(f"{fp['ref']}: no graphics on {layer}")
    a = np.array(pts)
    return (*a.min(0), *a.max(0))

def fp_layer_points(fp, layers):
    pts = []
    for g in fp['node']:
        if isinstance(g, list) and g and g[0].startswith('fp_'):
            lay = find1(g, 'layer')
            if lay and lay[1] in layers:
                pl = graphic_polyline(g, lambda p: fp_to_board(fp, *p))
                if pl: pts += pl
    return pts

# --------------------------------------------------------------------------------------
# 2D / 3D helpers
# --------------------------------------------------------------------------------------
def polys_of(geom):
    if geom is None or geom.is_empty: return []
    if geom.geom_type == 'Polygon': return [geom]
    if hasattr(geom, 'geoms'): return [p for g in geom.geoms for p in polys_of(g)]
    return []

def prism(geom, z0, z1):
    rings = []
    for g in polys_of(geom):
        if g.area < 1e-6: continue
        rings.append(np.asarray(g.exterior.coords)[:-1])
        rings += [np.asarray(h.coords)[:-1] for h in g.interiors]
    if not rings: return Manifold()
    return CrossSection(rings, FillRule.EvenOdd).extrude(z1 - z0).translate([0, 0, z0])

def local_box(fp, x0, y0, x1, y1):
    return Polygon([fp_to_board(fp, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])

def place(m, fp, z=0.0):
    return m.rotate([0, 0, -fp['rot']]).translate([fp['x'], fp['y'], z])

def union_all(ms):
    ms = [m for m in ms if not m.is_empty()]
    if not ms: return Manifold()
    out = ms[0]
    for m in ms[1:]: out = out + m
    return out

def hexagon(c, af):
    r = af / math.sqrt(3)
    return Polygon([(c[0] + r * math.cos(math.radians(30 + 60 * i)), c[1] + r * math.sin(math.radians(30 + 60 * i))) for i in range(6)])

def trim_thin(m, min_feature, max_step=0.1):
    """Cut away slivers thinner than min_feature (seen from above), e.g. where a screw bore nearly
    breaks into the hood. Slices the part wherever its cross-section changes, takes each slice's
    morphological opening (shrink by half the size, grow back) and removes what doesn't survive.
    Tiny pieces are just rounded-off convex corners (>= ~87 deg) and are left alone."""
    if min_feature <= 0 or m.is_empty(): return m
    m = _trim_pass(m, min_feature, max_step)
    for _ in range(4):             # removing slivers can leave small islands (pins) behind
        before = m.volume()
        m = _trim_pass(m, min_feature, max_step, islands_only=True)
        if before - m.volume() < 1e-3: break
    return m

def _trim_pass(m, min_feature, max_step, islands_only=False):
    grow = 0.05                    # cuts overshoot this much so they leave no micron-scale facets
    r = min_feature / 2 + grow     # (mitred overshoot can reach 2 x grow)
    min_area = 0.25 * r * r        # a 90-degree corner loses 0.21 r^2 to the opening
    zs = np.unique(np.round(np.asarray(m.to_mesh().vert_properties)[:, 2], 4))
    lv = [zs[0]]
    for z in zs[1:]:
        if z - lv[-1] > 0.01: lv.append(z)
    lv[-1] = zs[-1]
    cuts = []
    for za, zb in zip(lv[:-1], lv[1:]):
        # sloped bands (countersinks, clip-relief taper) are re-sliced in thin sub-bands
        sloped = abs(m.slice(za + 0.003).area() - m.slice(zb - 0.003).area()) > 1e-3
        n = max(1, math.ceil((zb - za) / max_step)) if sloped else 1
        for k in range(n):
            z0, z1 = za + (zb - za) * k / n, za + (zb - za) * (k + 1) / n
            thin = CrossSection()
            for z in (z0 + 0.003, (z0 + z1) / 2, z1 - 0.003):
                for comp in m.slice(z).decompose():
                    core = comp.offset(-r, JoinType.Round)
                    if core.is_empty():          # a sliver/island that is thin all over
                        thin = thin + comp; continue
                    if islands_only: continue
                    for q in (comp - core.offset(r, JoinType.Round)).decompose():
                        if q.area() > min_area: thin = thin + q
            if not thin.is_empty():
                # cuts at the very top/bottom poke out so they share no face with the part
                c0 = z0 - (1.0 if za == lv[0] and k == 0 else 0.0)
                c1 = z1 + (1.0 if zb == lv[-1] and k == n - 1 else 0.0)
                cuts.append(thin.offset(grow, JoinType.Miter).extrude(c1 - c0).translate([0, 0, c0]))
    if not cuts: return m
    # the cuts can leave zero-volume crumbs where neighbouring sub-bands meet; drop them
    # (simplify also collapses the zero-thickness films coplanar cut faces can leave behind)
    bodies = sorted((m - union_all(cuts)).simplify(0.001).decompose(), key=lambda q: -q.volume())
    keep = [q for q in bodies if q.volume() > 1.0] or bodies[:1]
    return Manifold.compose(keep) if len(keep) > 1 else keep[0]

# --------------------------------------------------------------------------------------
# Board half
# --------------------------------------------------------------------------------------
class Half:
    def __init__(self, prof, side):
        self.prof, self.side = prof, side
        pcb = sparse(open(os.path.join(HERE, prof['pcb'])).read())
        x0, x1 = prof['halves'][side]
        self.pcb2d = board_region(pcb).intersection(box(x0, -1e4, x1, 1e4))
        self.pcb2d = max(polys_of(self.pcb2d), key=lambda p: p.area)
        inside = lambda f: x0 < f['x'] < x1
        fps = [f for f in footprints(pcb) if inside(f)]
        rx = lambda k: re.compile(prof[k], re.I)
        self.switches = [f for f in fps if rx('switch_fp').search(f['lib'])]
        self.mounts = []
        for f in fps:
            if rx('mount_fp').search(f['lib']):
                d = max([p['drill'] or 0 for p in pads(f)] + [0])
                self.mounts.append((f['x'], f['y'], d))
        ign = rx('ignore_fp')
        self.others = [f for f in fps if f not in self.switches and not rx('mount_fp').search(f['lib'])
                       and not ign.search(f['lib'])]
        # profile parts -> 2D regions in board coords
        self.parts = []
        for spec in prof['parts']:
            for f in fps:
                if re.search(spec['fp'], f['lib'], re.I):
                    bx = spec.get('box')
                    if 'auto' in spec:
                        x0_, y0_, x1_, y1_ = fp_local_bbox(f, spec['auto']); m_ = spec.get('margin', 0)
                        bx = (x0_ - m_, y0_ - m_, x1_ + m_, y1_ + m_)
                    self.parts.append(dict(spec, fp_obj=f, box=bx, poly=local_box(f, *bx)))
        handled = {id(p['fp_obj']) for p in self.parts}
        self.unhandled = [f for f in self.others if id(f) not in handled]
        # things hanging under the PCB: sockets, B-side parts, pin tails
        obs = []
        for f in fps:
            if ign.search(f['lib']) or rx('mount_fp').search(f['lib']): continue
            pd = pads(f)
            bpts = [(p['x'], p['y']) for p in pd if any(l in ('B.Cu', '*.Cu') for l in p['layers'])]
            if f in self.switches:
                pts = bpts + [(p['x'], p['y']) for p in pd if p['drill'] and p['drill'] > 2.5]
                if len(pts) >= 3: obs.append(MultiPoint(pts).convex_hull.buffer(1.6))
                for p in pd:
                    if p['drill']: obs.append(Point(p['x'], p['y']).buffer(p['drill'] / 2 + 0.3))
            else:
                g = fp_layer_points(f, ('B.CrtYd',)) or fp_layer_points(f, ('B.Fab',)) + bpts
                if f['layer'] == 'B.Cu' and len(g) >= 3: obs.append(MultiPoint(g).convex_hull.buffer(0.3))
                for p in pd:
                    if p['drill']: obs.append(Point(p['x'], p['y']).buffer(max(p['size']) / 2 + 0.4))
        obs += [p['poly'] for p in self.parts if p['kind'] == 'below']
        self.under = unary_union(obs)

    # ------------------------------------------------------------------
    def build(self):
        p = P
        sw = self.switches
        hood_parts = [q for q in self.parts if q['kind'] == 'hood']
        self.hood_in = unary_union([q['poly'] for q in hood_parts]).buffer(p['hood_clear'], join_style=2) \
            if hood_parts else Polygon()
        hood_top_in = max([q['z'][1] for q in hood_parts], default=0) + p['hood_clear']
        self.hood_out = self.hood_in.buffer(p['hood_wall'], join_style=1)
        self.inner = self.pcb2d.buffer(p['gap'], join_style=1)
        self.outer = unary_union([self.pcb2d.buffer(p['gap'] + p['wall'], join_style=1), self.hood_out])
        zb = -p['pcb_t'] - p['cav'] - p['floor']
        self.zb = zb

        cutouts = unary_union([local_box(f, -p['cut'] / 2, -p['cut'] / 2, p['cut'] / 2, p['cut'] / 2) for f in sw])
        keycaps = unary_union([local_box(f, -p['keycap'][0] / 2 - p['keycap_clear'], -p['keycap'][1] / 2 - p['keycap_clear'],
                                         p['keycap'][0] / 2 + p['keycap_clear'], p['keycap'][1] / 2 + p['keycap_clear']) for f in sw])
        fl = p['flange'] / 2 + p['flange_clear']
        flanges = unary_union([local_box(f, -fl, -fl, fl, fl) for f in sw])
        self.cutouts, self.keycaps = cutouts, keycaps

        # ---------------- top shell ----------------
        t = p['slab_t']; c = p['edge_chamfer']; steps = 3
        pos = [prism(self.outer, 0, t - c)]
        for i in range(steps):
            pos.append(prism(self.outer.buffer(-c * (i + 1) / steps, join_style=1), t - c + c * i / steps, t - c + c * (i + 1) / steps))
        if not self.hood_in.is_empty:
            # cut the hood footprint out of the plate and add the hood slightly larger, so the two
            # overlap by volume (touching-only geometry breaks once the STL is re-merged)
            slab = union_all(pos) - prism(self.hood_out, -1, 50)
            hood = prism(self.hood_out.buffer(0.05, join_style=2), 0, hood_top_in + p['hood_roof']) - union_all([
                prism(keycaps, p['keycap_pressed_z'] - 0.3, 50), prism(flanges, t, 50)])
            pos = [slab, hood]
        top = union_all(pos)
        neg = [prism(cutouts, -1, t + 1)]
        w0, w1 = p['relief_w0'], p['relief_w1']
        ry = p['cut'] + 0.1
        rel = (CrossSection.square([w0, ry], center=True).extrude(p['relief_z'], scale_top=(w1 / w0, 1.0))
               + CrossSection.square([w0, ry], center=True).extrude(1.0).translate([0, 0, -1.0])
               + CrossSection.square([w1, ry], center=True).extrude(p['ledge_z'] - p['relief_z'] + 0.05).translate([0, 0, p['relief_z'] - 0.05]))
        neg += [place(rel, f) for f in sw]
        if not self.hood_in.is_empty:
            neg.append(prism(self.hood_in, -1, hood_top_in))
        for q in self.parts:
            if q['kind'] == 'pocket':
                neg.append(prism(q['poly'].buffer(0.3), -1, q['z'][1] + 0.3))
            elif q['kind'] == 'hole':
                neg.append(prism(q['poly'], -1, 60))
            elif q['kind'] == 'slot':
                neg.append(prism(q['poly'], q['z'][0], q['z'][1]))
        for (x, y, d) in self.mounts:
            neg.append(Manifold.cylinder(t + 2, p['screw_d'] / 2, circular_segments=48).translate([x, y, -1]))
            r0, r1 = p['screw_d'] / 2, p['csk_d'] / 2
            neg.append(Manifold.cylinder(r1 - r0 + 0.001, r0, r1, circular_segments=48).translate([x, y, t - (r1 - r0)]))
            neg.append(Manifold.cylinder(5, r1, circular_segments=48).translate([x, y, t]))
        untrimmed = top - union_all(neg)
        self.top = trim_thin(untrimmed, p['min_feature'])
        self.trimmed = dict(top=round(untrimmed.volume() - self.top.volume(), 2))

        # ---------------- base tray ----------------
        ztop = -p['seam_drop']; zf = zb + p['floor']; zpcb = -p['pcb_t']
        pos = [prism(self.outer, zb, zf), prism(self.outer.difference(self.inner), zb, ztop)]
        neg = []
        self.boss_info = []
        under_z = -p['pcb_t'] - p['under_h']          # sockets / pin tails end here
        r_low = max(p['boss_d'] / 2, p['nut_af'] / math.sqrt(3) + 0.9)
        for (x, y, d) in self.mounts:
            # full-size below the sockets (holds the nut), trimmed around parts above
            up2d = Point(x, y).buffer(p['boss_d'] / 2, 48).difference(self.under.buffer(p['min_clear']))
            up2d = max(polys_of(up2d), key=lambda g: g.distance(Point(x, y)) * -1e3 + g.area, default=Polygon())
            ring = up2d.difference(Point(x, y).buffer(max(d, p['screw_d']) / 2 + 0.05)).area if not up2d.is_empty else 0
            self.boss_info.append(dict(x=round(x, 2), y=round(y, 2), pcb_hole=d, support_mm2=round(ring, 1)))
            pos.append(Manifold.cylinder(under_z - 0.1 - zf + 0.002, r_low, circular_segments=48).translate([x, y, zf - 0.001]))
            pos.append(prism(up2d, under_z - 0.1 - 0.001, zpcb))
            neg.append(Manifold.cylinder(30, p['screw_d'] / 2, circular_segments=48).translate([x, y, zb - 1]))
            neg.append(prism(hexagon((x, y), p['nut_af']), zb - 1, zb + p['nut_depth']))
        # pillars under every switch, as close as possible to the preferred spot
        cands = [(0, 5)] + sorted(((u, v) for u in np.arange(-6, 6.1, 1.0) for v in np.arange(-6, 6.1, 1.0)),
                                  key=lambda q: math.hypot(q[0], q[1] - 5))
        rp = p['pillar_d'] / 2
        safe = self.pcb2d.buffer(-rp - 0.5)
        bosses = unary_union([Point(x, y).buffer(r_low + 0.8) for (x, y, d) in self.mounts])
        self.pillars = []
        for f in sw:
            for u, v in cands:
                q = Point(fp_to_board(f, u, v))
                if safe.contains(q) and self.under.distance(q) >= rp + p['min_clear'] and not bosses.contains(q) \
                        and all(q.distance(o) > 2 * rp + 1.5 for o in self.pillars):
                    self.pillars.append(q); break
        for q in self.pillars:
            pos.append(Manifold.cylinder(zpcb - zf + 0.001, rp, circular_segments=32).translate([q.x, q.y, zf - 0.001]))
        for q in self.parts:
            if q['kind'] == 'below':
                neg.append(prism(q['poly'].buffer(0.4), q['z'][0] - 0.3, zpcb))
            elif q['kind'] == 'slot':
                neg.append(prism(q['poly'], q['z'][0], q['z'][1]))
        if p['feet_d'] > 0:
            minx, miny, maxx, maxy = self.pcb2d.bounds
            for cx, cy in ((minx + 8, miny + 8), (maxx - 8, miny + 8), (minx + 8, maxy - 8), (maxx - 8, maxy - 8)):
                pt = Point(cx, cy)
                if self.pcb2d.buffer(-5).contains(pt):
                    neg.append(Manifold.cylinder(p['feet_depth'] + 1, p['feet_d'] / 2, circular_segments=48).translate([cx, cy, zb - 1]))
        untrimmed = union_all(pos) - union_all(neg)
        self.base = trim_thin(untrimmed, p['min_feature'])
        self.trimmed['base'] = round(untrimmed.volume() - self.base.volume(), 2)
        # PCB area each boss actually supports around its screw (after trimming)
        top_cs = self.base.slice(zpcb - 0.05)
        for b, (x, y, d) in zip(self.boss_info, self.mounts):
            disc = lambda rad: CrossSection.circle(rad, 48).translate([x, y])
            b['support_mm2'] = round((top_cs ^ disc(p['boss_d'] / 2)).area()
                                     - (top_cs ^ disc(max(d, p['screw_d']) / 2 + 0.05)).area(), 1)
        return self

    # ------------------------------------------------------------------
    def film(self):
        """Optional switch film (like the sheet under the Toucan's plate): a thin plastic sheet
        between the PCB and the top shell. It covers exactly where the top-shell STL touches the
        PCB, inset by film_clear from every opening and from the PCB edge."""
        c, mw = P['film_clear'], P['film_min']
        contact = Polygon()
        for r in self.top.slice(0.002).to_polygons():     # rings never cross: even-odd fill
            if len(r) >= 3: contact = contact.symmetric_difference(Polygon(r))
        f0 = contact.buffer(-c, join_style=2).intersection(self.pcb2d.buffer(-c, join_style=2))
        f1 = f0.buffer(-mw / 2, join_style=2).buffer(mw / 2, join_style=2).intersection(f0)
        pieces = sorted((q.simplify(1e-4) for q in polys_of(f1) if q.area >= 5.0), key=lambda q: -q.area)
        self.film2d = MultiPolygon(pieces)
        bb = box(*self.outer.buffer(5).bounds)
        clear = min(self.film2d.distance(bb.difference(contact)), self.film2d.distance(bb.difference(self.pcb2d))) \
            if pieces else 0.0
        x0, y0, x1, y1 = self.film2d.bounds if pieces else (0, 0, 0, 0)
        self.film_info = dict(size_mm=[round(x1 - x0, 1), round(y1 - y0, 1)], pieces=len(pieces),
                              area_cm2=round(self.film2d.area / 100, 1), clearance_mm=round(clear, 3),
                              ok=bool(pieces) and clear >= c - 1e-3)
        return self

    # ------------------------------------------------------------------
    def keepouts(self):
        """Solid stand-ins for everything the case must not touch (assembly coordinates)."""
        p = P; ko = {}
        ko['pcb'] = prism(self.pcb2d, -p['pcb_t'], 0)
        sw = self.switches
        ko['switch_lower'] = union_all([place(CrossSection.square([13.8, 13.8], center=True).extrude(p['slab_t'] - 0.02), f, 0.01) for f in sw])
        ko['switch_upper'] = union_all([place(CrossSection.square([p['flange'], p['flange']], center=True).extrude(3.3), f, p['slab_t'] + 0.01) for f in sw])
        ko['keycaps_pressed'] = union_all([place(CrossSection.square(list(p['keycap']), center=True).extrude(7), f, p['keycap_pressed_z']) for f in sw])
        ko['under_pcb'] = prism(self.under.intersection(self.pcb2d), -p['pcb_t'] - p['under_h'], -p['pcb_t'] - 0.01)
        for q in self.parts:
            if q['kind'] in ('hood', 'pocket', 'below'):
                ko.setdefault('part_' + q['kind'], []).append(prism(q['poly'], q['z'][0] + 0.01, q['z'][1]))
        return {k: union_all(v) if isinstance(v, list) else v for k, v in ko.items()}

# --------------------------------------------------------------------------------------
def switch_coupon():
    """Plate sample with the case's switch cutout (2 dots) plus 0.1 mm tighter (1 dot) and looser
    (3 dots) versions: order it with the case to see how the service's prints fit your switches."""
    p = P; t = p['slab_t']; sizes = (p['cut'] - 0.1, p['cut'], p['cut'] + 0.1); pitch = 19.0
    W = pitch * len(sizes) + 3; H = 22.0
    plate = prism(box(0, 0, W, H), 0, t)
    neg = []
    w0, w1 = p['relief_w0'], p['relief_w1']
    for i, s in enumerate(sizes):
        cx = 1.5 + pitch * (i + 0.5); cy = H / 2 + 1
        f = dict(x=cx, y=cy, rot=0.0)
        neg.append(prism(box(cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2), -1, t + 1))
        rel = (CrossSection.square([w0, s + 0.1], center=True).extrude(p['relief_z'], scale_top=(w1 / w0, 1.0))
               + CrossSection.square([w0, s + 0.1], center=True).extrude(1.0).translate([0, 0, -1.0])
               + CrossSection.square([w1, s + 0.1], center=True).extrude(p['ledge_z'] - p['relief_z'] + 0.05).translate([0, 0, p['relief_z'] - 0.05]))
        neg.append(place(rel, f))
        for k in range(i + 1):
            neg.append(Manifold.cylinder(1, 0.6, circular_segments=24).translate([cx + 2.5 * (k - i / 2), 1.6, t - 0.4]))
    return trim_thin(plate - union_all(neg), p['min_feature'])

def near_groups(P, eps):
    """Label points so that points closer than ~eps (per axis) share a label."""
    lab = np.arange(len(P)); cells = []
    for off in np.array(np.meshgrid([0, .5], [0, .5], [0, .5])).reshape(3, -1).T:
        inv = np.unique(np.floor(P / eps + off).astype(np.int64), axis=0, return_inverse=True)[1]
        cells.append(inv.reshape(-1))
    while True:
        old = lab.copy()
        for inv in cells:
            low = np.full(inv.max() + 1, len(P)); np.minimum.at(low, inv, lab); lab = low[inv]
        if (lab == old).all(): return lab

def to_trimesh(m, eps=1e-3, nudge=0.005):
    """Manifold -> trimesh that survives STL export (which merges vertices by position).
    1) Vertices closer than eps (1 um) are snapped together; the zero-length edges (slivers manifold
       occasionally leaves behind) are then collapsed wherever that keeps the surface a
       manifold (link condition).
    2) Where two solids only touch along an edge/point, manifold keeps the touching vertices
       separate (same position, different index); STL would merge them into a non-manifold
       edge, so each remaining copy is nudged 5 um towards its own faces."""
    mesh = m.to_mesh()
    V = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64)
    F = np.array(mesh.tri_verts, dtype=np.int64)
    grp = near_groups(V, eps)
    V = V[grp]
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    zero = E[grp[E[:, 0]] == grp[E[:, 1]]]
    vf = [set() for _ in range(len(V))]
    for fi in np.unique(np.where(np.isin(F, zero))[0]):
        for v in F[fi]: vf[v].add(fi)
    rep = np.arange(len(V)); alive = np.ones(len(F), bool); collapsed = 0
    def root(i):
        while rep[i] != i: i = rep[i]
        return i
    for a, b in zero:
        a, b = root(a), root(b)
        if a == b: continue
        fa, fb = vf[a], vf[b]
        shared = fa & fb
        if len(shared) != 2: continue
        opp = {int(v) for f in shared for v in F[f]} - {a, b}
        link = ({int(v) for f in fa for v in F[f]} - {a}) & ({int(v) for f in fb for v in F[f]} - {b})
        if link != opp: continue                  # collapsing would pinch the surface
        for f in shared:
            alive[f] = False
            for v in F[f]: vf[v].discard(f)
        for f in fb:
            F[f][F[f] == b] = a; fa.add(f)
        vf[b] = set(); rep[b] = a; collapsed += 1
    F = F[alive]
    used = np.unique(F)
    cnt = np.bincount(grp[used], minlength=len(V))
    pinched = used[cnt[grp[used]] > 1]
    if len(pinched):
        acc = np.zeros_like(V); n = np.zeros(len(V))
        for k in range(3):
            np.add.at(acc, F[:, k], V[F].mean(axis=1)); np.add.at(n, F[:, k], 1)
        d = acc[pinched] / n[pinched, None] - V[pinched]
        V[pinched] += nudge * d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
    tm = trimesh.Trimesh(vertices=V, faces=F, process=False)
    tm.remove_unreferenced_vertices()
    left = len(np.unique(near_groups(tm.vertices, eps)))
    tm.metadata.update(pinched=int(len(pinched)), collapsed=collapsed, coincident=len(tm.vertices) - left)
    return tm

def export(m, path, drop_to_bed=True):
    """Mirror KiCad's y-down frame to a real-world y-up frame and export."""
    m = m.mirror([0, 1, 0])
    if drop_to_bed:
        b = m.bounding_box()
        m = m.translate([-b[0], -b[1], -b[2]])
    tm = to_trimesh(m)
    tm.export(path)
    rt = trimesh.load(path)          # what a slicer sees (float32, vertices merged by position)
    ok = bool(rt.is_watertight and rt.is_winding_consistent and rt.volume > 0)
    print(f'  wrote {os.path.basename(path)}: {len(rt.faces)} tris, {rt.extents.round(1).tolist()} mm, '
          f'STL watertight={ok}' + (f" (unpinched {tm.metadata['pinched']} verts, collapsed "
                                    f"{tm.metadata['collapsed']} zero-length edges)" if ok else ''))
    return ok

def check(name, m, keepouts, tol=1e-3):
    tm = to_trimesh(m)
    res = dict(part=name, watertight=bool(tm.is_watertight), bodies=len(m.decompose()),
               volume_cm3=round(float(tm.volume) / 1000, 2),
               size_mm=[round(float(v), 1) for v in tm.extents], interference={})
    for k, ko in keepouts.items():
        v = (m ^ ko).volume()
        res['interference'][k] = round(v, 4)
    res['ok'] = res['watertight'] and res['bodies'] == 1 and all(v <= tol for v in res['interference'].values())
    return res

# --------------------------------------------------------------------------------------
def _svg_d(g, tr):
    return ' '.join('M' + ' L'.join('%.3f,%.3f' % tr(x, y) for x, y in ring.coords[:-1]) + ' Z'
                    for q in polys_of(g) for ring in [q.exterior, *q.interiors])

def _dxf(path, rings):
    """Minimal DXF (R12, millimetres): one closed POLYLINE per cut loop."""
    L = ['0', 'SECTION', '2', 'HEADER', '9', '$ACADVER', '1', 'AC1009', '9', '$INSUNITS', '70', '4',
         '9', '$MEASUREMENT', '70', '1', '0', 'ENDSEC', '0', 'SECTION', '2', 'ENTITIES']
    for r in rings:
        L += ['0', 'POLYLINE', '8', '0', '66', '1', '10', '0.0', '20', '0.0', '30', '0.0', '70', '1']
        for x, y in r:
            L += ['0', 'VERTEX', '8', '0', '10', f'{x:.4f}', '20', f'{y:.4f}', '30', '0.0']
        L += ['0', 'SEQEND', '8', '0']
    with open(path, 'w') as fh:
        fh.write('\n'.join(L + ['0', 'ENDSEC', '0', 'EOF']) + '\n')

def write_film(halves, out, board):
    """Switch-film cutting files (all halves, seen from the switch side; KiCad's y-down = SVG's):
    a 1:1 print template with a scale bar, and the bare outlines as SVG + DXF for cutting machines."""
    hs = [h for h in halves if h.film_info['pieces']]
    if not hs: return []
    svg = lambda w, h, body: (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.3f}mm" height="{h:.3f}mm" '
                              f'viewBox="0 0 {w:.3f} {h:.3f}">\n' + '\n'.join(body) + '\n</svg>\n')
    txt = lambda x, y, s, size=2.6, bold=False: (f'<text x="{x:.2f}" y="{y:.2f}" font-family="sans-serif" font-size="{size}"'
                                                 + (' font-weight="bold"' if bold else '') + f'>{s}</text>')
    # printable template, halves stacked (180 mm wide: fits Letter and A4 with the printer's margins)
    m, W = 10.0, 180.0
    y = m + 3
    el = [txt(m, y, f'Switch film cutting template: {board}', 3.4, True)]
    y += 7
    el.append(f'<path d="M{m},{y} h50 M{m},{y - 1.5} v3 ' + ' '.join(f'M{m + 10 * i},{y - 1} v2' for i in range(1, 5))
              + f' M{m + 50},{y - 1.5} v3" stroke="#000" stroke-width="0.3"/>')
    el.append(txt(m + 53, y + 1, '50 mm: print at 100% / actual size, then measure this bar'))
    y += 1.5
    for line in ('Seen from the switch side. Tape the film over this sheet and cut on the black lines:',
                 'grey = film (keep), white = cut out, red + = screw hole centre.'):
        y += 4.5; el.append(txt(m, y, line))
    for h in hs:
        x0, y0, x1, y1 = h.film2d.bounds
        n = h.film_info['pieces']
        y += 9
        el.append(txt(m, y, f'{h.side.upper()} half: {x1 - x0:.1f} x {y1 - y0:.1f} mm' + (f', {n} pieces' if n > 1 else ''), 3.0, True))
        y += 4
        tr = lambda x, yy, ox=m + (W - 2 * m - (x1 - x0)) / 2 - x0, oy=y - y0: (x + ox, yy + oy)
        el.append(f'<path d="{_svg_d(h.film2d, tr)}" fill="#dcdcdc" fill-rule="evenodd" stroke="#000" stroke-width="0.15"/>')
        for (mx, my, _) in h.mounts:
            cx, cy = tr(mx, my)
            el.append(f'<path d="M{cx - 1.2:.3f},{cy:.3f} h2.4 M{cx:.3f},{cy - 1.2:.3f} v2.4" stroke="#c0392b" stroke-width="0.12"/>')
        y += y1 - y0
    y += 9
    el.append(txt(m, y, f'Film = where the top-shell STL touches the PCB, {P["film_clear"]} mm smaller all round. '
                        'Use 0.10-0.13 mm (4-5 mil) PET film.', 2.2))
    files = [os.path.join(out, f'{board}_film_template_1to1.svg'), os.path.join(out, f'{board}_film_cut.svg'),
             os.path.join(out, f'{board}_film_cut.dxf')]
    with open(files[0], 'w') as fh:     # white page: stays readable where it's shown on a dark background
        fh.write(svg(W, y + m, [f'<rect width="{W:.3f}" height="{y + m:.3f}" fill="#fff"/>'] + el))
    # bare outlines, halves stacked (105 mm wide: fits even a Cricut Joy's 4.5 in mat), no margin
    # or text (a cutter would cut text; a tight page makes the imported size the films' size)
    gap = 10.0
    Wc = max(h.film2d.bounds[2] - h.film2d.bounds[0] for h in hs)
    body, rings, y = [], [], 0.0
    for h in hs:
        x0, y0, x1, y1 = h.film2d.bounds
        tr = lambda px, py, ox=-x0, oy=y - y0: (px + ox, py + oy)
        body.append(f'<path d="{_svg_d(h.film2d, tr)}" fill="#000" fill-rule="evenodd"/>')
        rings += [[tr(*pt) for pt in ring.coords[:-1]] for q in polys_of(h.film2d) for ring in [q.exterior, *q.interiors]]
        y += y1 - y0 + gap
    Hc = y - gap
    with open(files[1], 'w') as fh:
        fh.write(svg(Wc, Hc, body))
    _dxf(files[2], [[(u, Hc - v) for u, v in r] for r in rings])        # DXF is y-up
    return files

# --------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--board', default=next(iter(PROFILES)), choices=list(PROFILES))
    ap.add_argument('--out', default=os.path.join(HERE, 'stl'))
    ap.add_argument('--sides', nargs='+', default=['left', 'right'])
    ap.add_argument('--no-preview', action='store_true')
    a = ap.parse_args()
    prof = PROFILES[a.board]
    os.makedirs(a.out, exist_ok=True)
    report = dict(board=a.board, params=P, halves={})
    halves = []
    for side in a.sides:
        print(f'[{side}] building ...')
        h = Half(prof, side).build().film(); halves.append(h)
        if h.unhandled:
            print('  ! top-side parts without a profile entry:', sorted({f['lib'] for f in h.unhandled}))
        ko = h.keepouts()
        r_top = check('top', h.top, ko); r_base = check('base', h.base, ko)
        for r in (r_top, r_base):
            r['thin_trimmed_mm3'] = h.trimmed[r['part']]
            print(f"  {r['part']:4s} watertight={r['watertight']} bodies={r['bodies']} vol={r['volume_cm3']}cm3 "
                  f"size={r['size_mm']} trimmed<{P['min_feature']}mm={r['thin_trimmed_mm3']}mm3 "
                  f"clash={ {k: v for k, v in r['interference'].items() if v > 1e-3} } -> {'OK' if r['ok'] else 'CHECK'}")
        stem = os.path.join(a.out, f'{a.board}_{side}')
        r_top['stl_ok'] = export(h.top, stem + '_top.stl'); r_base['stl_ok'] = export(h.base, stem + '_base.stl')
        fi = h.film_info
        print(f"  film {fi['size_mm'][0]} x {fi['size_mm'][1]} mm, {fi['pieces']} piece(s), {fi['clearance_mm']} mm "
              f"from every top-shell opening and the PCB edge -> {'OK' if fi['ok'] else 'CHECK'}")
        report['halves'][side] = dict(top=r_top, base=r_base, switches=len(h.switches), mounts=h.boss_info,
                                      pillars=len(h.pillars), unhandled=sorted({f['lib'] for f in h.unhandled}),
                                      film=fi)
    export(switch_coupon(), os.path.join(a.out, 'switch_fit_coupon.stl'))
    for f in write_film(halves, a.out, a.board):
        print('  wrote', os.path.basename(f))
    with open(os.path.join(a.out, f'{a.board}_report.json'), 'w') as fh:
        json.dump(report, fh, indent=1, default=str)
    if not a.no_preview:
        from preview import render_all
        render_all(halves, a.out, a.board, P)
    print('done ->', a.out)

if __name__ == '__main__':
    main()
