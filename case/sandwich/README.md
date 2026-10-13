# Sandwich case: Ferris Sweep Bling LP (wireless)

The [enclosed case](../enclosed/README.md) with a Totemist-style top. The keycaps sit in wells and
the case rim comes up to just under their tops, so from the side the keyboard reads as one solid
block instead of keycaps standing on a plate. That's the profile of ErgoMech's Totemist and of
GEIST's open-source TOTEM it's derived from. ErgoMech calls this a sandwich case.

![preview](stl/sweep-bling-lp_preview.png)

## What it keeps from the enclosed case

Everything that makes the enclosed case work stays the same:

- **Switch plate:** a 2.2 mm plate sits flat on the PCB, with the same 14 mm holes and clip
  reliefs, so the switches snap in and can't work loose.
- **Base tray:** the same tray, M2 hex-nut pockets and support pillars. Its outline grows by up
  to 2.5 mm along the pinky and front edges, where the rim needs room beside the keycaps.
- **Screws:** the same 4 × M2×8 countersunk screws per half go down through the top shell, the PCB
  and the base into the nuts. Their heads sit on the same seat in the plate, at the bottom of a
  4.7 mm hole in the rim.
- **Openings:** the same USB-C slot, power-switch slot and paper-clip hole for the reset button,
  and the optional [switch film](#switch-film-optional).
- **Electronics:** the nice!nano and battery sit under the rim's roof instead of a raised hood, so
  nothing on the board is visible from outside.

## What's new: the height

The rim's height is copied from the TOTEM case (measured from GEIST's STEP files), and the Totemist
follows the TOTEM:

| Above the PCB top | Height |
|---|---|
| Plate top (well floor) | 2.2 mm |
| Choc v1 stem top, unpressed | 8.0 mm |
| **Rim top** | **9.05 mm** (TOTEM's: 6.85 mm above the plate) |
| MBK keycap top | 10.5 mm, so the caps stand **1.45 mm** above the rim, as on your Totemist |

On the desk it's 15.3 mm to the rim and 16.7 mm to the keycap tops. That's the same keycap height
as the enclosed case (the PCB and switches don't move) and just under the Totemist's 17 mm. For a
rim exactly level with MBK tops, regenerate with `--rim 10.5` (see
[Regenerating](#regenerating-or-tweaking)).

![side profile: enclosed vs sandwich](stl/sweep-bling-lp_profile.png)

Also copied from the TOTEM and Totemist:

- **Wells:** 1.0 mm between every keycap and the wall, a 0.5 mm chamfer on the rim's inside edges
  and a 1.5 mm round on the outside edge. Where two columns are staggered, the wall steps with them.
- **Thumb shelf:** in front of the thumb keys there is no rim, just the plate, so the wall can't
  catch your thumbs.
- **Hollow rim:** the rim is a 1.5 mm roof on its walls, open underneath, so it's light and cheap to
  print. There are no closed cavities to trap resin.

New for this board:

- **Ribs under the roof** every 12 mm, resting on the PCB, so pressing on the rim feels as solid as
  the Forager's plate, and no bridge is wider than 12 mm if it's ever printed on a filament printer
  (the bay over the nice!nano is the one exception, at 17 mm).
- **Curb at the nice!nano:** the nano sits 0.46 mm from the inner column's keycaps, too close for a
  wall. The wall above it stops just over the nano, and a 1 mm curb on the plate keeps liquid on the
  plate from running into the nano's bay.

## Files (`stl/`)

| File | Upload? | What it is |
|---|---|---|
| `sweep-bling-lp_left_top.stl`, `sweep-bling-lp_right_top.stl` | yes | Top shells: 113.6 × 91.7 × 9.05 mm, 15.7 cm³ each |
| `sweep-bling-lp_left_base.stl`, `sweep-bling-lp_right_base.stl` | yes | Base trays: 113.6 × 91.7 × 6.0 mm, 17.4 cm³ each |
| [`../enclosed/stl/switch_fit_coupon.stl`](../enclosed/stl/switch_fit_coupon.stl) | optional | Switch-hole sample. The plate is the enclosed case's, so the same coupon applies |
| `sweep-bling-lp_film_template_1to1.svg`, `_film_cut.svg`, `_film_cut.dxf` | no | Switch film for this top shell |
| `sweep-bling-lp_preview.png`, `sweep-bling-lp_profile.png` | no | Renders and side views |
| `sweep-bling-lp_report.json` | no | Automated check results |

## What to buy

The same as the enclosed case: see its [What to buy](../enclosed/README.md#what-to-buy) for links.

- **Keyboard:** your current keebmaker Sweep Bling LP (wireless) build. Run the enclosed case's
  [Before ordering](../enclosed/README.md#before-ordering) checks first: same PCB, same templates.
- 8 × M2×8 countersunk screws (ISO 10642, 90° head), 8 × plain M2 hex nuts (DIN 934), and a
  1.3 mm hex key long enough to reach 7 mm down the screw holes.
- MBK keycaps or any Choc-spaced cap up to 17.5 × 16.5 mm. Taller caps stand further above the rim.
- Optional: rubber bumpers, and the [switch film](../enclosed/README.md#shopping-list) supplies.

## Ordering from JLCPCB

Order it like the enclosed case ([Ordering from JLCPCB](../enclosed/README.md#ordering-from-jlcpcb)):
SLA resin, **JLC Black Resin**, quantity 1 of each of the 4 files, default finish, no paint. It's
about 66 cm³ of resin, so expect roughly US$25–60 plus shipping; JLC's quote is the real number.
Use this remark instead:

```text
Mechanical keyboard case: 4 parts. The parts screw together, so accuracy matters.
- *_top files: please keep supports and support marks off the top of the rim, the floors of the
  key wells around the 14 mm square holes, and the outer side walls. Supports inside the hollow
  underside are fine.
- *_base files: supports on the outside bottom are fine. Please keep them off the inside
  (the pillar and boss tops hold the PCB).
- The 14 mm square holes, the small ledges under them and the hex pockets are functional.
  Please don't fill, repair or scale the models.
If a part can't be printed this way, please contact me before printing. Thank you!
```

Nothing is thinner than 0.8 mm (the generator trims anything thinner). If JLC asks about small
holes, they're deliberate: the 1.8 mm reset hole and the 2.4 mm screw holes.

## When the parts arrive

1. Clean off support marks, especially on the well floors around the switch holes, the ledges
   under them, the nut pockets and the boss tops. Sand wet if you sand.
2. Test a switch in a corner hole of the top shell. It should click in and stay put upside down.
   If it's too tight, file the hole lightly; don't force it, resin cracks.
3. Test-fit the PCB in the base.

## Assembly

1. Pull all keycaps and switches. If the board is still in keebmaker's tray, take it out.
2. Put an M2 nut into each hex pocket under the base (tape holds a loose one).
3. Set the PCB in the base, hotswap sockets down.
4. Optional: lay the switch film on the PCB.
5. Put the top shell on, nano under the roof at the inner edge. Drive the 4 screws down through the
   holes in the rim with the hex key until the PCB can't move, then **stop**: fingertip force only.
6. Push each switch through its well into the plate until it clicks, then fit the keycaps.
7. To use:
   - **Power switch:** through the USB-C opening with a toothpick, as on the enclosed case.
   - **Reset/bootloader:** a paper clip through the small hole in the rim's roof next to the thumbs.
8. Optional: rubber bumpers underneath.

Each keycap has 1 mm of room to the wall, as on the Totemist. To pull one, lift an edge with a
fingernail or a thin plastic pry tool, or use the switch puller.

## Switch film (optional)

The enclosed case's [switch film](../enclosed/README.md#switch-film-optional) works here too, cut
from this folder's files: `stl/sweep-bling-lp_film_template_1to1.svg` (print at 100 %) or
`_film_cut.svg` / `_film_cut.dxf` for a cutting machine. It covers where this top shell's plate
touches the PCB, 0.3 mm smaller all round, so the pieces differ from the enclosed case's. Same
film, tools and method.

## Regenerating or tweaking

From `case/sandwich/`, with the same environment as the enclosed case (plus `rtree` for the
pictures):

```sh
python3 -m venv .venv
.venv/bin/pip install manifold3d shapely trimesh numpy matplotlib rtree
.venv/bin/python generate_case.py              # ~25 s, writes stl/
.venv/bin/python generate_case.py --rim 10.5   # rim level with MBK keycap tops
.venv/bin/python generate_case.py --help
```

`generate_case.py` reads the board and builds the base and plate with the enclosed case's
generator (`../enclosed/generate_case.py`, whose `P` dict still sets the plate, base and screw
sizes), then adds the rim with `sandwich.py`. `sandwich.py` is the same file in the Forager and
Fortemis repos. Useful settings:

| Setting | Where | Default | Effect |
|---|---|---|---|
| `--rim` | command line | 9.05 | Rim height above the PCB top. 10.5 = level with MBK tops |
| `cap_clear` | `Sandwich(...)` in `sandwich.py` | 1.0 | Keycap-to-wall gap |
| `roof`, `wall`, `inner_wall` | `Sandwich(...)` | 1.5, 1.6, 1.2 | Rim roof, outer wall and well wall thickness |
| `shelf` | `Sandwich(...)` | True | Thumb shelf; False gives the thumbs a full-height wall in front |
| `ribs` | `Sandwich(...)` | (12, 1.2) | Rib pitch and width under the roof; None for an open hollow |
| `RIM_MIN` | `generate_case.py` | 2.5 | Narrowest rim around the main keys; the outline grows to make room |
| `NANO_GAP` | `generate_case.py` | 0.45 | Keycap-to-wall gap along the nice!nano |

Every run checks that each part is one watertight solid with no closed pockets, and that the top
shell keeps clear of the PCB, the switches, the keycaps over their full travel, the nice!nano,
battery, TRRS jack and reset button, and the USB-C and reset openings. Results are printed and saved
to `stl/sweep-bling-lp_report.json`. Don't upload anything marked `CHECK`.

## Assumptions and limits

- **Same board build as the enclosed case:** nano face-down on low-profile headers with the LiPo
  under it, at most 5.6 mm above the PCB. The roof is 7.55 mm above the PCB, so there's room to spare.
- **Keycaps:** sized for MBK (17.5 × 16.5 × 3.98 mm). Smaller caps fit with more gap.
- **Sweat:** the plate still covers the PCB everywhere but under the switches, and the roof covers
  the electronics. But the wells hold drops on the plate where a flat plate lets them run off its
  edge, the same as on the Totemist, so wipe it down. The curb and the optional film help. See
  [KEYBOARD-MOISTURE-PLAN.md](../../../KEYBOARD-MOISTURE-PLAN.md).
- **The nice!nano edge:** beside the inner column the well wall can't reach the plate, because the
  nano sits only 0.46 mm from the keycaps. Along that edge there's a slot from the curb top
  (3.2 mm above the PCB) to the wall's lower edge (6.0 mm, just above the nano). The enclosed case has
  a similar slit there. Drops on the plate have to climb the curb to get in.
- **License:** `../pcb/sweepbling-lp.kicad_pcb` is from davidphilipbarr/Sweep (Solderpad Hardware
  License v2.1). The rim heights and clearances follow GEIGEIGEIST/TOTEM's case (CERN-OHL-P-2.0).
