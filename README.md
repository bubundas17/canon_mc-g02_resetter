# Canon MC-G02 Maintenance Cartridge Resetter

Reset the chip on a Canon **MC-G02** (and compatible) maintenance cartridge so you can clean and reuse it instead of buying a new one every time the printer says it is full.

<img src="https://github.com/wangyu-/canon_mc-g02_resetter/blob/ee0e90a86b5609ec6eb443d971a5ddca6e544e4c/images/for_readme.jpg" width="500">

## Platform guides (wiki)

| Platform | Guide |
|----------|--------|
| **Raspberry Pi Pico** (recommended) | [wiki/Raspberry-Pi-Pico.md](wiki/Raspberry-Pi-Pico.md) |
| **Raspberry Pi Zero W** | [wiki/Raspberry-Pi-Zero-W.md](wiki/Raspberry-Pi-Zero-W.md) |
| **Arduino** (original) | [wiki/Arduino.md](wiki/Arduino.md) |
| Overview | [wiki/Home.md](wiki/Home.md) |

---

## Background

Canon PIXMA G-series printers store waste ink in a **maintenance cartridge**. When it fills, the printer stops printing.

Canon does not measure ink volume with a sensor. The cartridge has an **EEPROM chip** that logs usage. Even after you empty/clean the cartridge, the chip still reports “full.”

This project talks to that chip over **I2C** and rewrites it so the printer treats the cartridge as empty again.

### Compatible cartridges / printers

**MC-G02** (and often **MC-G01** with the same tools), used on printers such as:

| Region | Examples |
|--------|----------|
| US | G620, G1220, G2260, G3260 |
| China | G580, G680, G1820, G2820, G2860, G3820, G3860 |
| Others | Similar PIXMA G models that use MC-G02 / MC-G01 |

Chip markings seen in the wild: `416RT` (ST **M24C16-R**), also `G16` / `4G16` (compatible).

---

## How the reset works

The EEPROM is **2048 bytes** (M24C16), laid out roughly as:

| Offset | Size | Contents |
|--------|------|----------|
| `0x000–0x07F` | 128 bytes | Identity / serial (two mirrored 64-byte headers) |
| `0x080–0x2FF` | 640 bytes | Usage log (two mirrored 320-byte sections) |
| `0x300–0x7FF` | 1280 bytes | Larger usage log (two mirrored 640-byte sections) |

Each section’s little-endian 16-bit words **sum to `0xA5A5`** (checksum).

A **new/empty** cartridge has usage sections that look like `A5 A5` followed by zeros. There is **no single “ink level” byte** to clear.

| Method | Platforms | Needs empty dump? |
|--------|-----------|-------------------|
| **`zero_usage`** (keep serial, clear usage tables) | Pico, Pi Zero W, Arduino Mega/ESP32/R4 | **No** |
| **Clone dump/write** | All (Arduino Uno OK) | **Yes** |

---

## Project layout

```text
canon_mc-g02_resetter/
├── pico/                 # Pico MicroPython — zero_usage + LED
├── pi/                   # Pi Zero W — zero-usage + reset failsafe
├── arduino/
│   ├── sketch_zero_usage/    # zero_usage (Mega/ESP32/R4/…)
│   ├── sketch_hack_read/     # classic dump
│   └── sketch_hack_write/    # classic clone write
├── wiki/                 # Platform guides
└── README.md
```

---

## Quick start

1. **Pico** — [wiki/Raspberry-Pi-Pico.md](wiki/Raspberry-Pi-Pico.md): `MODE = "zero_usage"`.
2. **Pi Zero W** — [wiki/Raspberry-Pi-Zero-W.md](wiki/Raspberry-Pi-Zero-W.md): `python3 mc_g02_resetter.py zero-usage`.
3. **Arduino** — [wiki/Arduino.md](wiki/Arduino.md): upload `arduino/sketch_zero_usage` (or classic read/write on Uno).

---

## Safety notes

1. Use **3.3V** on Pico/Pi for the chip. Do not feed 5V from those boards.
2. Keep a backup dump before experimenting.
3. Dump twice and compare when capturing important images.
4. Clean/dry the physical cartridge; resetting the chip alone does not remove ink.
5. Some printers reject foreign cloned serials; Pico `zero_usage` keeps the chip’s own header.
6. Unofficial and unsupported by Canon. Use at your own risk.

---

## Credits

- Original Arduino project: [wangyu-/canon_mc-g02_resetter](https://github.com/wangyu-/canon_mc-g02_resetter)
- EEPROM layout / checksum notes: [issue #2](https://github.com/wangyu-/canon_mc-g02_resetter/issues/2)
- ST M24C16 datasheet and community 24Cxx Arduino examples

## License

See [LICENSE](LICENSE).
