# Canon MC-G02 Resetter Wiki

Reset the EEPROM chip on a Canon **MC-G02** / **MC-G01** maintenance cartridge so you can clean and reuse it.

## Choose your platform

| Guide | Best for | Needs empty ROM dump? |
|-------|----------|------------------------|
| [Raspberry Pi Pico](Raspberry-Pi-Pico.md) | Easiest; LED feedback; recommended | **No** (`zero_usage`) |
| [Raspberry Pi Zero W](Raspberry-Pi-Zero-W.md) | Headless Pi + Python | Yes (clone dump/write) |
| [Arduino](Arduino.md) | Original method | Yes (clone dump/write) |

## Quick background

The printer does not measure waste-ink volume. It reads a counter/log stored in an **M24C16** I2C EEPROM (2048 bytes) on the cartridge. Cleaning the sponge alone does not clear that chip.

- **Pico `zero_usage`:** keeps the chip serial/header, clears usage tables to the empty layout.
- **Arduino / Pi clone:** write back a ROM image dumped from a new/empty cartridge.

## Safety

- Pico / Pi: power the chip from **3.3V**, not 5V.
- Always keep a backup dump before experimenting.
- Resetting the chip does not remove ink — clean/dry the cartridge as needed.
- Unofficial / unsupported by Canon. Use at your own risk.

## Source code

- Repo: [bubundas17/canon_mc-g02_resetter](https://github.com/bubundas17/canon_mc-g02_resetter)
- Original Arduino project: [wangyu-/canon_mc-g02_resetter](https://github.com/wangyu-/canon_mc-g02_resetter)
