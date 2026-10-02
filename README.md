# Ferris Sweep ZMK config

ZMK config for the Ferris Sweep, built on ZMK's own `cradio` shield. The keymap is
[config/cradio.keymap](config/cradio.keymap).

# Dongle mode (PandaKB USB dongle)

The keyboard can also run through [PandaKB's ZMK dongle](https://pandakb.com/shop/keyboard-kit/pandakb-zmk-split-keyboard-dongle/)
(a nice!nano v2 with a 1.3" OLED). The dongle becomes the split **central** and both halves become its
**peripherals**: plug it into a computer and the keyboard just works as a USB keyboard, with no Bluetooth pairing
on that computer. ZMK fixes each part's role at build time, so in dongle mode the halves cannot connect to a
computer without the dongle, and switching modes means reflashing. Both sets of firmware are built.

| Artifact | Flash to | Mode |
|---|---|---|
| `cradio_dongle` | dongle | dongle |
| `cradio_left_dongle_mode` | left half | dongle |
| `cradio_right-nice_nano_v2-zmk` | right half | **both** (the right half is a peripheral either way) |
| `cradio_left-nice_nano_v2-zmk` | left half | standalone |
| `settings_reset-nice_nano_v2-zmk` | any of the three | reset (all are nice!nanos) |

**One-time setup:** turn off other ZMK keyboards nearby, flash the settings reset to all three devices
(standalone-mode bonds must be cleared first), then flash the dongle-mode firmware, plug in the dongle, and power
on both halves. To go back, reset the halves and flash the standalone left firmware.

- Keymap changes then only need the **dongle** reflashed. To reach its bootloader without opening its case, hold
  both far outer thumbs (maintenance layer) and hold `T` for 2 seconds. `Q`/`P` still bootloader each half.
- The dongle keeps all five Bluetooth profiles (its connection limits are raised to fit both halves too), so it
  can also pair to computers wirelessly on its own battery.
- Layers are named so the dongle's OLED can show them. The dongle never deep-sleeps: deep sleep is only woken by
  a key press, and it has no keys.
- [boards/shields/cradio/](boards/shields/cradio/) holds only the dongle. It copies the Ferris layout and matrix
  transform from ZMK v0.3.0's `cradio.dtsi`, since every part of a split must match; re-check it if ZMK is
  upgraded. The `pandakb_dongle` shield holds the OLED wiring, copied from PandaKB's own dongle firmware.
