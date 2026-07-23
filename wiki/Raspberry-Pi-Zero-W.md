# Raspberry Pi Zero W guide

Feature-complete Python tool: **zero-usage** reset (no virgin dump), plus clone reset with backup/restore failsafe.

Code: [`pi/mc_g02_resetter.py`](https://github.com/bubundas17/canon_mc-g02_resetter/tree/main/pi)

---

## What you need

- Raspberry Pi Zero W / Zero 2 W (or Pi 3/4/5)
- Raspberry Pi OS with I2C enabled
- microSD with bootable OS
- Jumper wires to chip pads
- Optional: 2× 10kΩ pull-ups (usually **not** needed on GPIO2/3)

---

## Enable I2C

```bash
sudo raspi-config
# Interface Options → I2C → Enable
```

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

Use **3.3V only**. On-board pull-ups on GPIO2/3 are normally enough.

Power via **PWR IN** micro-USB (or 5V on header pins 2/4 + GND). Prefer a solid 5V supply.

---

## Commands

### Recommended reset (no empty ROM needed)

```bash
python3 mc_g02_resetter.py scan
python3 mc_g02_resetter.py zero-usage
```

This will:

1. Double-read the chip  
2. Save `backup.bin`  
3. Keep header/serial, clear usage tables (`A5 A5` + zeros)  
4. Write + verify  
5. Restore `backup.bin` automatically if verify fails  

Optional:

```bash
python3 mc_g02_resetter.py zero-usage --backup my_backup.bin --save-empty empty_built.bin
```

### Clone reset (needs a fresh/empty dump)

```bash
python3 mc_g02_resetter.py dump -o fresh.bin --twice   # only on a NEW cartridge
python3 mc_g02_resetter.py reset -i fresh.bin          # later, on a full cartridge
```

`reset` also saves `backup.bin` and restores it if verify fails.

### Low-level tools

```bash
python3 mc_g02_resetter.py dump -o rom.bin --twice
python3 mc_g02_resetter.py write -i rom.bin      # no auto-backup
python3 mc_g02_resetter.py verify -i rom.bin
```

Permission errors: `sudo python3 ...` or add your user to the `i2c` group.

---

## How to know it worked

- Console prints `OK — usage cleared...` (or clone OK).  
- Exit code `0` = success, `2` = failed write but backup restored, `1` = hard fail.  
- Printer maintenance level should show empty / OK after reinstalling the cartridge.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| I2C bus not found | Enable I2C, reboot |
| `scan` finds nothing | Wiring, 3.3V, contacts; `i2cdetect -y 1` |
| Double-read mismatch | Bad contacts / wiring |
| Permission denied | `sudo` or `i2c` group |

---

## See also

- [Home](Home.md)
- [Raspberry Pi Pico](Raspberry-Pi-Pico.md)
- [Arduino](Arduino.md)
