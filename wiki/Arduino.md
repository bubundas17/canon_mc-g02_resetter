# Arduino guide

Original method from [wangyu-/canon_mc-g02_resetter](https://github.com/wangyu-/canon_mc-g02_resetter): dump the EEPROM with one sketch, later write that image back with another.

Code:

- [`sketch_hack_read/`](https://github.com/bubundas17/canon_mc-g02_resetter/tree/main/sketch_hack_read)
- [`sketch_hack_write/`](https://github.com/bubundas17/canon_mc-g02_resetter/tree/main/sketch_hack_write)

> This is a **clone** reset: you need a ROM dumped from a **new/empty** cartridge (or a known-good empty image).  
> If you do not have one, use the [Raspberry Pi Pico](Raspberry-Pi-Pico.md) `zero_usage` mode instead.

---

## What you need

- Arduino with I2C (Uno, Nano, etc.)
- Arduino IDE
- 2× **10kΩ** pull-up resistors
- Wires to the cartridge chip pads

---

## Wiring

| Chip pad | Arduino Uno / Nano |
|----------|---------------------|
| VCC | 5V or 3.3V (match your board / chip tolerance; M24C16-R accepts both) |
| GND | GND |
| SDA | SDA (**A4** on Uno) |
| SCL | SCL (**A5** on Uno) |

Pull-ups:

```text
VCC ----[10k]---- SDA ---- chip SDA
VCC ----[10k]---- SCL ---- chip SCL
```

Upload the **read** sketch **before** connecting the chip when possible, so the running firmware is known-good at first contact.

Wiring photos from the original project: [upstream wiki](https://github.com/wangyu-/canon_mc-g02_resetter/wiki).

---

## Dump the ROM (`sketch_hack_read`)

1. Open `sketch_hack_read/sketch_hack_read.ino` in Arduino IDE.
2. Select board + port, upload.
3. Connect the chip.
4. Open **Serial Monitor** at **9600** baud.
5. You should see a C array, 2048 bytes:

```text
const unsigned char my_rom1[] PROGMEM=
{
0xXX,0xXX,...
};
```

6. Dump **twice** and confirm both dumps are identical.
7. Save the array for later (this is your reset image if dumped while empty/new).

If you see `Wire Not Ready!!!`, fix wiring/contacts/pull-ups.

---

## Write / reset (`sketch_hack_write`)

1. Open `sketch_hack_write/sketch_hack_write.ino`.
2. Paste your saved `my_rom1[]` array in place of the placeholder comment.
3. Upload and run with the chip connected.
4. Serial output shows page progress, then a verification dump.
5. Confirm the verification dump matches the ROM you wrote (eyeball or `diff` / `vimdiff`).

The sketch writes in **16-byte pages** with a short delay (M24C16 page program), then reads back all 2048 bytes.

---

## How the sketches work

Both use the Arduino `Wire` (I2C) library against base address `0x50`.

- High bits of the byte offset go into the I2C address (`0x50`…`0x57`).
- Low 8 bits are the word address inside that block.

**Read** loops `0 … 2047` and prints hex.  
**Write** pages the pasted image, then dumps for verify.

There is no “set counter to 0” logic — only full-image clone.

---

## Workflow summary

```text
New/empty chip  --read-->  my_rom1 dump  --save-->
Full chip       --write my_rom1-->  printer sees empty again
```

1. Dump early (while cartridge is still empty/new).
2. Clean sponge when full.
3. Write the saved dump.
4. Verify, reinstall.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `Wire Not Ready!!!` | SDA/SCL/VCC/GND, 10k pull-ups, solid contacts |
| Dumps differ between runs | Bad wiring; dump again until two match |
| Write verify mismatch | Power/contacts; retry; confirm `my_rom1` pasted correctly |
| Printer rejects cartridge | Some firmware dislikes foreign serials; try Pico `zero_usage` keeping original header |

---

## See also

- [Home](Home.md)
- [Raspberry Pi Pico](Raspberry-Pi-Pico.md)
- [Raspberry Pi Zero W](Raspberry-Pi-Zero-W.md)
