# Canon MC-G02 Maintenance Cartridge Resetter

Reset the chip on a Canon **MC-G02** (and compatible) maintenance cartridge so you can clean and reuse it instead of buying a new one every time the printer says it is full.

<img src="https://github.com/wangyu-/canon_mc-g02_resetter/blob/ee0e90a86b5609ec6eb443d971a5ddca6e544e4c/images/for_readme.jpg" width="500">

Original Arduino method: [Wiki](https://github.com/wangyu-/canon_mc-g02_resetter/wiki)  
This repo also includes **Raspberry Pi Pico** (recommended) and **Raspberry Pi** Python tools.

---

## Background

Canon PIXMA G-series printers store waste ink in a **maintenance cartridge**. When it fills, the printer stops printing.

Canon does not measure ink volume with a sensor. The cartridge has an **EEPROM chip** that logs usage. Even after you empty/clean the cartridge, the chip still reports “full.”

This project talks to that chip over **I2C** and rewrites it so the printer treats the cartridge as empty again.

### Compatible cartridges / printers

**MC-G02** (and often **MC-G01** with the same sketches), used on printers such as:

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

A **new/empty** cartridge has usage sections that look like:

- first two bytes: `A5 A5`
- remaining bytes: `00`

There is **no single “ink level” byte** to set to zero. Usage is an encoded log that grows as the printer runs cleanings. Almost the whole usage area changes over time.

### Reset strategies

| Method | What it does | Needs empty dump? |
|--------|----------------|-------------------|
| **`zero_usage` (Pico)** | Keeps this chip’s serial/header; clears usage tables to empty layout + valid checksums | **No** |
| **Clone dump** (Arduino / `fresh.bin`) | Writes a full image dumped from a new/empty chip | **Yes** |

`zero_usage` is the easiest path if you do not have a virgin cartridge dump.

---

## Project layout

```text
canon_mc-g02_resetter/
├── sketch_hack_read/          # Arduino: dump EEPROM → Serial
├── sketch_hack_write/         # Arduino: write pasted dump → chip
├── pico/                      # Raspberry Pi Pico (MicroPython) — recommended
│   ├── main.py                # Auto-start loop on boot
│   └── mc_g02_resetter.py     # Read / zero_usage / reset / LED UI
├── pi/                        # Raspberry Pi Zero/3/4 (Linux + smbus2)
│   ├── mc_g02_resetter.py
│   └── requirements.txt
├── wifi/Home.md               # Original wiki-style docs
└── README.md
```

---

## Recommended: Raspberry Pi Pico

Works well, cheap, USB-powered. Default mode clears usage tables **without** needing a fresh ROM file.

### What you need

- Raspberry Pi Pico (or Pico H) with **MicroPython**
- 2× **10kΩ** resistors (I2C pull-ups — required on Pico)
- Jumper wires / soldering to the cartridge chip pads
- Thonny IDE (or any MicroPython tool)

### Flash MicroPython

1. Hold **BOOTSEL**, plug Pico into USB, release BOOTSEL  
2. Copy a Pico UF2 (e.g. from [micropython.org](https://micropython.org/download/RPI_PICO/)) onto the `RPI-RP2` drive  
3. Pico reboots into MicroPython  

### Wiring

| Chip pad | Pico | Notes |
|----------|------|--------|
| VCC | **3V3** (pin 36) | Use 3.3V only — not VBUS/5V |
| GND | **GND** (pin 38) | |
| SDA | **GP4** (pin 6) | |
| SCL | **GP5** (pin 7) | |
| — | 10k from SDA → 3V3 | Pull-up |
| — | 10k from SCL → 3V3 | Pull-up |

```text
3V3 ----[10k]---- SDA ---- chip SDA
3V3 ----[10k]---- SCL ---- chip SCL
3V3 -------------- chip VCC
GND -------------- chip GND
```

### Install the scripts

In Thonny:

1. **View → Files**
2. Save both files **onto the Pico**:
   - `pico/mc_g02_resetter.py`
   - `pico/main.py`
3. Soft-reboot / power-cycle the Pico (`main.py` starts the loop automatically)

Or open `mc_g02_resetter.py` and click **Run**.

### Modes (`MODE` in `mc_g02_resetter.py`)

```python
MODE = "zero_usage"   # default — clear usage, keep serial
```

| Mode | Purpose |
|------|---------|
| `zero_usage` | Read → backup → clear usage tables → verify (restore on failure) |
| `dump` | Read chip → `backup.bin` only |
| `capture_fresh` | Save a real new/empty chip as `fresh.bin` |
| `reset` | Write `fresh.bin` onto chip (clone method) |
| `write` | Write `fresh.bin` without the full clone failsafe flow |

### LED feedback (onboard GP25)

| Pattern | Meaning |
|---------|---------|
| Blink | Ready — waiting for chip |
| Solid | Working (read / write / verify) |
| 5 short flashes, then off | Done — success |
| 2 blink → pause → 2 blink | Error |
| Solid after error | Restoring `backup.bin` |
| 10 fast flashes, then off | Restore finished |

### Typical Pico workflow

1. Remove cartridge from printer; remove / expose the chip  
2. Wire chip to Pico (pull-ups on)  
3. Power Pico — LED blinks (ready)  
4. Connect chip — LED goes solid, then **5 flashes** if OK  
5. Clean/dry the sponge if needed; reinstall chip + cartridge  
6. Printer should report maintenance cartridge empty / OK  

**Failsafe:** before writing, the Pico saves `backup.bin`. If verify fails, it restores the backup automatically.

### REPL helpers (optional)

```python
import mc_g02_resetter as r
r.scan()
r.dump("check.bin")
r.run_loop()          # same as main loop
```

---

## Arduino (original method)

Requires a dump from a **new/empty** cartridge (or a known-good empty image), then write that image back later.

### Prerequisites

- Arduino with I2C (e.g. Uno: SDA/SCL = A4/A5)
- Two **10kΩ** pull-ups on SDA and SCL to VCC
- Arduino IDE

### Wiring

Same chip pads: **VCC, GND, SDA, SCL** + 10k pull-ups to VCC.  
See images in the [Wiki](https://github.com/wangyu-/canon_mc-g02_resetter/wiki).

### Dump (`sketch_hack_read`)

1. Upload `sketch_hack_read` **before** connecting the chip (safer)  
2. Connect chip  
3. Serial Monitor @ **9600** baud  
4. Copy the printed `my_rom1[]` array (2048 bytes)  
5. Dump **twice** and confirm both dumps match  

### Write / reset (`sketch_hack_write`)

1. Paste the saved array into `sketch_hack_write.ino` as `my_rom1[]`  
2. Upload and run  
3. Sketch writes in 16-byte pages, then dumps again for verification  
4. Confirm the verification dump matches your source ROM  

---

## Raspberry Pi (Zero / 3 / 4 / 5)

Linux + `smbus2`. Pi Zero W has onboard I2C pull-ups on GPIO2/3 — external 10k often optional.

### Setup

```bash
sudo raspi-config   # Interface Options → I2C → Enable
cd pi
pip3 install -r requirements.txt
```

### Wiring (Pi Zero / header)

| Chip | Pi |
|------|-----|
| VCC | 3.3V (pin 1) |
| GND | GND (pin 6) |
| SDA | GPIO2 (pin 3) |
| SCL | GPIO3 (pin 5) |

### Commands

```bash
python3 mc_g02_resetter.py scan
python3 mc_g02_resetter.py dump -o rom.bin
python3 mc_g02_resetter.py dump -o rom.c --format c
python3 mc_g02_resetter.py write -i rom.bin    # clone write + verify
python3 mc_g02_resetter.py verify -i rom.bin
```

The Pi script is a **clone dump/write** tool (like the Arduino sketches). For header-preserving empty reset without a virgin dump, use the **Pico `zero_usage`** mode.

---

## Safety notes

1. Use **3.3V** on Pico/Pi. Do not feed 5V into the chip from those boards.  
2. Always keep a backup dump (`backup.bin` / Arduino serial dump) before experimenting.  
3. Dump twice and compare when capturing important images.  
4. Clean/dry the physical cartridge; resetting the chip alone does not remove ink.  
5. Some printers/firmware may reject foreign cloned serials; `zero_usage` avoids that by keeping the chip’s own header.  
6. This project is unofficial and unsupported by Canon. Use at your own risk.

---

## Q&A

**Why didn’t dump alone reset the cartridge?**  
Dump only reads. Reset requires writing an empty layout (`zero_usage`) or cloning a fresh dump.

**Can I reset by zeroing one counter byte?**  
No. Usage is a large encoded log with checksums, not a single level field.

**Do I need a brand-new cartridge for Pico `zero_usage`?**  
No. That mode builds the empty usage pattern from the chip you plug in.

**Why pull-ups?**  
I2C needs them. Pico: add 10k. Pi Zero W default I2C pins: usually already pulled up on-board. Arduino: add 10k.

**MC-G01?**  
Users report the same Arduino flow works for MC-G01. Pico `zero_usage` uses the same empty-section layout; verify on your printer.

---

## Credits

- Original Arduino project: [wangyu-/canon_mc-g02_resetter](https://github.com/wangyu-/canon_mc-g02_resetter)  
- EEPROM layout / checksum notes from community discussion ([issue #2](https://github.com/wangyu-/canon_mc-g02_resetter/issues/2))  
- References in the original wiki: ST M24C16 datasheet, Arduino 24Cxx examples  

## License

See [LICENSE](LICENSE).
