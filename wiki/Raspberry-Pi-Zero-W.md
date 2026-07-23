# Raspberry Pi Zero W guide

Use a Raspberry Pi Zero W (or Zero 2 W / other Pi with I2C) to dump and write the MC-G02 EEPROM with Python.

Code: [`pi/mc_g02_resetter.py`](https://github.com/bubundas17/canon_mc-g02_resetter/tree/main/pi)

> This tool is a **clone dump/write** helper (same idea as Arduino).  
> For clearing usage **without** a virgin ROM, prefer the [Raspberry Pi Pico](Raspberry-Pi-Pico.md) `zero_usage` mode.

---

## What you need

- Raspberry Pi Zero W / Zero 2 W (or Pi 3/4/5)
- Raspberry Pi OS with I2C enabled
- microSD with bootable OS (Zero does not boot from USB alone)
- Jumper wires to chip pads
- Optional: 2× 10kΩ pull-ups (often **not** needed on GPIO2/3 — board has pull-ups)

---

## Enable I2C

```bash
sudo raspi-config
# Interface Options → I2C → Enable
# Reboot if prompted
```

Install dependency:

```bash
cd pi
pip3 install -r requirements.txt
# or: sudo apt install python3-smbus2
```

---

## Wiring (40-pin header)

| Chip pad | Pi Zero W | Physical pin |
|----------|-----------|----------------|
| VCC | **3.3V** | 1 |
| GND | **GND** | 6 |
| SDA | **GPIO2 (SDA)** | 3 |
| SCL | **GPIO3 (SCL)** | 5 |

```text
Chip VCC  -> Pin 1  (3.3V)
Chip SDA  -> Pin 3  (GPIO2)
Chip SCL  -> Pin 5  (GPIO3)
Chip GND  -> Pin 6  (GND)
```

Use **3.3V only**. GPIO2/GPIO3 already have on-board pull-ups; extra 10k is usually optional.

### Power notes (Zero / Zero 2 W)

- Power via the **PWR IN** micro-USB (not the data/OTG port), or 5V on header pins 2/4 + GND.
- One green ACT LED indicates power/activity (no separate red power LED).
- Prefer a good 5V supply; weak PC USB ports often fail to boot.

---

## Commands

```bash
# Probe for M24C16 blocks (0x50..0x57)
python3 mc_g02_resetter.py scan

# Dump 2048 bytes
python3 mc_g02_resetter.py dump -o rom.bin
python3 mc_g02_resetter.py dump -o rom.c --format c

# Write a ROM image (clone reset) + verify
python3 mc_g02_resetter.py write -i rom.bin

# Compare chip to a file
python3 mc_g02_resetter.py verify -i rom.bin
```

If you get permission errors:

```bash
sudo python3 mc_g02_resetter.py scan
# or: sudo usermod -aG i2c $USER   # then log out/in
```

---

## Clone-reset workflow

1. Dump a **new/empty** cartridge early → keep `fresh.bin` / `rom.bin` safe. Dump **twice** and confirm identical.
2. When a cartridge is full, clean the sponge if needed.
3. `write -i fresh.bin` onto that chip.
4. `verify -i fresh.bin` (or rely on post-write verify).
5. Reinstall and check the printer.

Writing a dump taken from a **full** cartridge back onto itself does nothing useful.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| I2C bus not found | Enable I2C, reboot |
| `scan` finds nothing | Wiring, 3.3V, chip contact; try `i2cdetect -y 1` |
| Permission denied | `sudo` or add user to `i2c` group |
| Board dead / no LED | PWR port, cable, flashed SD, try GPIO 5V power |

---

## See also

- [Home](Home.md)
- [Raspberry Pi Pico](Raspberry-Pi-Pico.md) (recommended if you have a Pico)
- [Arduino](Arduino.md)
