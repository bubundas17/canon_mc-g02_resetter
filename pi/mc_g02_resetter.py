#!/usr/bin/env python3
"""
Canon MC-G02 maintenance cartridge EEPROM resetter for Raspberry Pi.

Chip: ST M24C16 (16 Kbit / 2048 bytes) over I2C.
Same protocol as the Arduino sketches in this repo.

Wiring (Pi Zero W):
  Chip VCC  -> 3.3V
  Chip GND  -> GND
  Chip SDA  -> GPIO2 (pin 3)   — on-board pull-ups present
  Chip SCL  -> GPIO3 (pin 5)

Enable I2C: sudo raspi-config -> Interface Options -> I2C
Install:    pip3 install -r requirements.txt
            or: sudo apt install python3-smbus2

Examples:
  python3 mc_g02_resetter.py scan
  python3 mc_g02_resetter.py dump -o rom.bin
  python3 mc_g02_resetter.py dump -o rom.c --format c
  python3 mc_g02_resetter.py write -i rom.bin
  python3 mc_g02_resetter.py verify -i rom.bin
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

try:
    from smbus2 import SMBus, i2c_msg
except ImportError:
    print(
        "Missing dependency: smbus2\n"
        "  pip3 install smbus2\n"
        "  or: sudo apt install python3-smbus2",
        file=sys.stderr,
    )
    sys.exit(1)

EEPROM_SIZE = 2048
BASE_ADDR = 0x50  # M24C16: 0x50..0x57 select 256-byte blocks
PAGE_SIZE = 16
WRITE_DELAY_S = 0.01  # 10 ms page write cycle (matches Arduino sketches)
DEFAULT_BUS = 1  # Pi Zero W uses I2C bus 1


def i2c_addr_for(offset: int) -> int:
    """Map byte offset to I2C address (upper address bits in device addr)."""
    return BASE_ADDR | (offset >> 8)


def word_addr(offset: int) -> int:
    return offset & 0xFF


def read_byte(bus: SMBus, offset: int) -> int:
    addr = i2c_addr_for(offset)
    wa = word_addr(offset)
    write = i2c_msg.write(addr, [wa])
    read = i2c_msg.read(addr, 1)
    try:
        bus.i2c_rdwr(write, read)
    except OSError as exc:
        raise RuntimeError(
            f"I2C read failed at offset {offset} (dev 0x{addr:02X}). "
            "Check wiring and that I2C is enabled."
        ) from exc
    return bytes(read)[0]


def read_all(bus: SMBus) -> bytearray:
    data = bytearray(EEPROM_SIZE)
    print("Start Dumping...")
    for i in range(EEPROM_SIZE):
        data[i] = read_byte(bus, i)
        if (i + 1) % 256 == 0:
            print(f"  read {i + 1}/{EEPROM_SIZE}")
    return data


def write_page(bus: SMBus, offset: int, page: bytes) -> None:
    if len(page) == 0 or len(page) > PAGE_SIZE:
        raise ValueError("page length must be 1..16")
    if offset % PAGE_SIZE != 0:
        raise ValueError("offset must be page-aligned")
    addr = i2c_addr_for(offset)
    payload = bytes([word_addr(offset)]) + bytes(page)
    try:
        bus.i2c_rdwr(i2c_msg.write(addr, payload))
    except OSError as exc:
        raise RuntimeError(
            f"I2C write failed at offset {offset} (dev 0x{addr:02X}). "
            "Check wiring and that I2C is enabled."
        ) from exc
    time.sleep(WRITE_DELAY_S)


def write_all(bus: SMBus, data: bytes) -> None:
    if len(data) != EEPROM_SIZE:
        raise ValueError(f"ROM must be exactly {EEPROM_SIZE} bytes, got {len(data)}")
    print("Start Writing Rom...")
    pages = EEPROM_SIZE // PAGE_SIZE
    for i in range(pages):
        if i % 16 == 0:
            print(f"current writing page:{i}")
        start = i * PAGE_SIZE
        write_page(bus, start, data[start : start + PAGE_SIZE])
    print("Write Done!")


def format_c_array(data: bytes, name: str = "my_rom1") -> str:
    lines = [f"const unsigned char {name}[] PROGMEM=", "{"]
    row = []
    for i, b in enumerate(data):
        row.append(f"0x{b:02X}")
        if len(row) == 32 or i == len(data) - 1:
            suffix = "," if i < len(data) - 1 else ""
            lines.append(",".join(row) + suffix)
            row = []
    lines.append("};")
    return "\n".join(lines) + "\n"


def parse_rom_file(path: Path) -> bytes:
    raw = path.read_bytes()
    # Binary dump
    if len(raw) == EEPROM_SIZE and b"0x" not in raw[:64]:
        return raw

    text = raw.decode("utf-8", errors="ignore")
    hex_bytes = re.findall(r"0x([0-9A-Fa-f]{2})", text)
    if len(hex_bytes) == EEPROM_SIZE:
        return bytes(int(h, 16) for h in hex_bytes)

    # Plain hex dump: "AA BB CC" or "AABBCC..."
    plain = re.findall(r"[0-9A-Fa-f]{2}", text)
    if len(plain) == EEPROM_SIZE and "0x" not in text:
        return bytes(int(h, 16) for h in plain)

    raise ValueError(
        f"Could not parse ROM from {path}: expected {EEPROM_SIZE} bytes "
        f"(binary) or {EEPROM_SIZE} hex values (C array / hex text)."
    )


def save_rom(path: Path, data: bytes, fmt: str) -> None:
    if fmt == "bin":
        path.write_bytes(data)
    elif fmt == "c":
        path.write_text(format_c_array(data), encoding="utf-8")
    elif fmt == "hex":
        lines = []
        for i in range(0, EEPROM_SIZE, 16):
            chunk = " ".join(f"{b:02X}" for b in data[i : i + 16])
            lines.append(f"{i:04X}: {chunk}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        raise ValueError(f"unknown format: {fmt}")
    print(f"Saved {len(data)} bytes to {path} ({fmt})")


def cmd_scan(bus: SMBus) -> int:
    print(f"Scanning I2C bus for M24C16 blocks 0x{BASE_ADDR:02X}..0x{BASE_ADDR + 7:02X}...")
    found = []
    for addr in range(BASE_ADDR, BASE_ADDR + 8):
        try:
            # Probe with a 0-byte write (same idea as i2cdetect)
            bus.i2c_rdwr(i2c_msg.write(addr, []))
            found.append(addr)
            print(f"  found 0x{addr:02X}")
        except OSError:
            pass
    if not found:
        print("No device found. Check wiring, power (3.3V), and I2C enable.")
        return 1
    if found == list(range(BASE_ADDR, BASE_ADDR + 8)):
        print("All 8 blocks present — chip looks good.")
    else:
        print(
            "Partial response (normal for some adapters). "
            "Try a dump; if it fails, recheck SDA/SCL."
        )
    return 0


def cmd_dump(bus: SMBus, out: Path, fmt: str) -> int:
    data = read_all(bus)
    print()
    print(format_c_array(data), end="")
    print("\nAll done! Save this dump and use it with the write command.")
    if out:
        save_rom(out, data, fmt)
    return 0


def cmd_write(bus: SMBus, rom_path: Path, skip_verify: bool) -> int:
    data = parse_rom_file(rom_path)
    write_all(bus, data)
    if skip_verify:
        return 0
    print("\nStart Dumping for Verification...")
    dumped = read_all(bus)
    if dumped == data:
        print("Verification OK — dump matches written ROM.")
        return 0
    mismatches = sum(1 for a, b in zip(data, dumped) if a != b)
    print(f"Verification FAILED — {mismatches} byte(s) differ.")
    return 1


def cmd_verify(bus: SMBus, rom_path: Path) -> int:
    expected = parse_rom_file(rom_path)
    dumped = read_all(bus)
    if dumped == expected:
        print("Match — chip contents equal ROM file.")
        return 0
    mismatches = sum(1 for a, b in zip(expected, dumped) if a != b)
    print(f"Mismatch — {mismatches} byte(s) differ.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Dump/write Canon MC-G02 (M24C16) cartridge chip on Raspberry Pi"
    )
    p.add_argument(
        "-b",
        "--bus",
        type=int,
        default=DEFAULT_BUS,
        help=f"I2C bus number (default: {DEFAULT_BUS})",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="Probe I2C for the EEPROM")

    dump = sub.add_parser("dump", help="Read full EEPROM (2048 bytes)")
    dump.add_argument("-o", "--output", type=Path, help="Output file path")
    dump.add_argument(
        "--format",
        choices=("bin", "c", "hex"),
        default="bin",
        help="Output format when -o is set (default: bin)",
    )

    write = sub.add_parser("write", help="Write a ROM dump to the chip (reset)")
    write.add_argument("-i", "--input", type=Path, required=True, help="ROM file (.bin or .c)")
    write.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip post-write verification dump",
    )

    verify = sub.add_parser("verify", help="Compare chip contents to a ROM file")
    verify.add_argument("-i", "--input", type=Path, required=True, help="ROM file (.bin or .c)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with SMBus(args.bus) as bus:
            if args.cmd == "scan":
                return cmd_scan(bus)
            if args.cmd == "dump":
                return cmd_dump(bus, args.output, args.format)
            if args.cmd == "write":
                return cmd_write(bus, args.input, args.no_verify)
            if args.cmd == "verify":
                return cmd_verify(bus, args.input)
    except PermissionError:
        print(
            "Permission denied opening I2C bus.\n"
            "  Try: sudo python3 mc_g02_resetter.py ...\n"
            "  Or add your user to the i2c group: sudo usermod -aG i2c $USER",
            file=sys.stderr,
        )
        return 1
    except FileNotFoundError:
        print(
            f"I2C bus {args.bus} not found. Enable I2C with raspi-config and reboot.",
            file=sys.stderr,
        )
        return 1
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
