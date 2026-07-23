# Arduino guide

Two approaches:

1. **`sketch_zero_usage`** (recommended) — clear usage tables, keep serial; backup + verify + restore  
2. **Classic clone** — `sketch_hack_read` / `sketch_hack_write` (needs a virgin dump)

---

## Option A — zero_usage (feature-complete)

Code: [`arduino/sketch_zero_usage/`](https://github.com/bubundas17/canon_mc-g02_resetter/tree/main/arduino/sketch_zero_usage)

Same algorithm as Pico / Pi Zero W:

1. Double-read chip into RAM backup  
2. Keep header/serial (`0x000–0x07F`)  
3. Write empty usage layout (`A5 A5` + zeros)  
4. Verify; on failure rewrite the backup  

### Board requirements

Needs enough SRAM for a 2048-byte backup (about **2.5KB+** free).

| Board | Supported? |
|-------|------------|
| Mega, Uno R4, ESP32, RP2040 (Arduino core), many ARM boards | Yes |
| Classic **Uno / Nano (ATmega328P)** | **No** — sketch refuses to compile; use Pico or Mega |

### Wiring

| Chip pad | Arduino |
|----------|---------|
| VCC | 5V or 3.3V (M24C16-R accepts both; match pull-up rail) |
| GND | GND |
| SDA | SDA (A4 on Uno-class) |
| SCL | SCL (A5 on Uno-class) |

Add **2× 10kΩ** pull-ups from SDA and SCL to VCC.

### Usage

1. Open `arduino/sketch_zero_usage/sketch_zero_usage.ino`  
2. Select a supported board + port  
3. Upload  
4. Open Serial Monitor at **115200** baud  
5. Connect the chip (or reset the board after connecting)  
6. Wait for `OK — usage cleared...` / `DONE`

On verify failure you should see failsafe restore messages; chip returns to the pre-write image.

---

## Option B — classic clone (original)

Code:

- [`arduino/sketch_hack_read/`](https://github.com/bubundas17/canon_mc-g02_resetter/tree/main/arduino/sketch_hack_read)
- [`arduino/sketch_hack_write/`](https://github.com/bubundas17/canon_mc-g02_resetter/tree/main/arduino/sketch_hack_write)

Works on classic Uno/Nano. You **must** dump a new/empty cartridge first.

### Dump (`sketch_hack_read`)

1. Upload **before** connecting the chip when possible  
2. Connect chip  
3. Serial Monitor @ **9600** baud  
4. Copy `my_rom1[]` (2048 bytes)  
5. Dump **twice**; confirm identical  

### Write (`sketch_hack_write`)

1. Paste `my_rom1[]` into the sketch  
2. Upload and run  
3. Confirm verification dump matches  

Wiring photos: [upstream wiki](https://github.com/wangyu-/canon_mc-g02_resetter/wiki).

---

## Which should I use?

| Goal | Sketch |
|------|--------|
| Reset without a virgin dump | **`sketch_zero_usage`** (Mega / ESP32 / R4 / …) |
| Only have a classic Uno + empty dump | `sketch_hack_read` + `sketch_hack_write` |
| Want simplest hardware path | [Raspberry Pi Pico](Raspberry-Pi-Pico.md) |

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Compile error about ATmega328P RAM | Use Mega/ESP32/R4 or Pico |
| Read fail / Wire errors | SDA/SCL/VCC/GND, 10k pull-ups |
| Double-read mismatch | Contacts / wiring |
| Verify failed + restore | Chip left as before; fix wiring and retry |

---

## See also

- [Home](Home.md)
- [Raspberry Pi Pico](Raspberry-Pi-Pico.md)
- [Raspberry Pi Zero W](Raspberry-Pi-Zero-W.md)
