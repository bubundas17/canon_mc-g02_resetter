# Raspberry Pi Pico guide

**Recommended method.** MicroPython on a Pico can clear the maintenance usage log **without** a virgin cartridge dump.

Code: [`pico/mc_g02_resetter.py`](https://github.com/bubundas17/canon_mc-g02_resetter/tree/main/pico) · [`pico/main.py`](https://github.com/bubundas17/canon_mc-g02_resetter/blob/main/pico/main.py)

---

## What you need

- Raspberry Pi Pico or Pico H
- MicroPython UF2 ([download](https://micropython.org/download/RPI_PICO/))
- 2× **10kΩ** resistors (I2C pull-ups — **required**)
- Jumper wires / soldering access to chip pads
- [Thonny](https://thonny.org/) (or another MicroPython IDE)

---

## Flash MicroPython

1. Unplug the Pico.
2. Hold **BOOTSEL**, plug into USB, then release BOOTSEL.
3. A drive named **RPI-RP2** appears.
4. Copy the `.uf2` file onto that drive.
5. Pico reboots into MicroPython (drive disappears).

---

## Wiring

| Chip pad | Pico | Physical pin |
|----------|------|----------------|
| VCC | **3V3** | 36 |
| GND | **GND** | 38 |
| SDA | **GP4** | 6 |
| SCL | **GP5** | 7 |

Pull-ups (required):

```text
3V3 ----[10k]---- SDA (GP4) ---- chip SDA
3V3 ----[10k]---- SCL (GP5) ---- chip SCL
3V3 ---------------------------- chip VCC
GND ---------------------------- chip GND
```

Use **3.3V only**. Do not use VBUS / 5V for the chip.

---

## Install scripts

In Thonny:

1. **Run → Select interpreter → MicroPython (Raspberry Pi Pico)**
2. **View → Files**
3. Save onto the Pico (not only on the PC):
   - `mc_g02_resetter.py`
   - `main.py`
4. Power-cycle or soft-reboot. `main.py` starts the loop automatically.

---

## Modes

Edit near the top of `mc_g02_resetter.py`:

```python
MODE = "zero_usage"   # default — recommended
```

| Mode | Purpose |
|------|---------|
| `zero_usage` | Read → `backup.bin` → clear usage tables → verify; restore backup on failure |
| `dump` | Read chip → `backup.bin` only |
| `capture_fresh` | Save a real new/empty chip as `fresh.bin` |
| `reset` | Write `fresh.bin` (full clone) |
| `write` | Write `fresh.bin` (simpler path) |

### How `zero_usage` works

1. Double-read the chip (must match) and save `backup.bin`.
2. Keep header/serial (`0x000–0x07F`).
3. Set usage sections to empty layout: `A5 A5` + zeros (valid `0xA5A5` checksums).
4. Write and verify.
5. On verify failure, restore `backup.bin`.

No separate empty ROM file is required.

---

## LED feedback (onboard GP25)

| Pattern | Meaning |
|---------|---------|
| Blink | Ready — waiting for chip |
| Solid | Working (read / write / verify) |
| 5 short flashes, then off | Done — success |
| 2 blink → pause → 2 blink | Error |
| Solid after error | Restoring `backup.bin` |
| 10 fast flashes, then off | Restore finished |

After success/error/restore, LED stays off until you unplug the chip; then it returns to ready blink.

---

## Typical workflow

1. Remove cartridge; expose chip pads.
2. Wire chip + pull-ups.
3. Power Pico — LED blinks (ready).
4. Connect chip — LED solid, then **5 flashes** if OK.
5. Clean/dry sponge if needed; reinstall chip + cartridge.
6. Confirm printer shows maintenance cartridge empty / OK.

---

## Optional REPL commands

```python
import mc_g02_resetter as r
r.scan()
r.dump("check.bin")
r.run_loop()
```

To download files from the Pico in Thonny: **View → Files** → under **Raspberry Pi Pico** → right-click → **Download to...**

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `scan()` finds nothing | Wiring, 3V3 (not 5V), both 10k pull-ups |
| LED stays blinking | Chip not detected / bad contact |
| Error pattern then restore | Write/verify failed; original data restored from `backup.bin` |
| Printer still says full | Confirm 5-flash success; reseat cartridge; clean contacts |

---

## See also

- [Home](Home.md)
- [Raspberry Pi Zero W](Raspberry-Pi-Zero-W.md)
- [Arduino](Arduino.md)
