#!/usr/bin/env python3
"""
Canon MC-G02 maintenance cartridge EEPROM resetter for Raspberry Pi.

Feature-complete (same flows as Pico):
  zero-usage  — clear usage tables, keep serial (no virgin dump needed)
  reset       — clone fresh.bin with backup/verify/restore failsafe
  dump/write/verify/scan — low-level tools

Chip: ST M24C16 (2048 bytes) over I2C.

Wiring (Pi Zero W):
  Chip VCC  -> 3.3V (pin 1)
  Chip GND  -> GND  (pin 6)
  Chip SDA  -> GPIO2 (pin 3)  — on-board pull-ups
  Chip SCL  -> GPIO3 (pin 5)

Enable I2C: sudo raspi-config -> Interface Options -> I2C
Install:    pip3 install -r requirements.txt

Examples:
  python3 mc_g02_resetter.py scan
  python3 mc_g02_resetter.py zero-usage
  python3 mc_g02_resetter.py reset -i fresh.bin
  python3 mc_g02_resetter.py dump -o rom.bin
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
BASE_ADDR = 0x50
PAGE_SIZE = 16
WRITE_DELAY_S = 0.01
DEFAULT_BUS = 1
DEFAULT_BACKUP = Path("backup.bin")


def i2c_addr_for(offset: int) -> int:
    return BASE_ADDR | (offset >> 8)


def word_addr(offset: int) -> int:
    return offset & 0xFF


def read_byte(bus: SMBus, offset: int) -> int:
    addr = i2c_addr_for(offset)
    write = i2c_msg.write(addr, [word_addr(offset)])
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
    print("Reading EEPROM...")
    for i in range(EEPROM_SIZE):
        data[i] = read_byte(bus, i)
        if (i + 1) % 256 == 0:
            print(f"  read {i + 1}/{EEPROM_SIZE}")
    return data


def read_twice(bus: SMBus) -> bytes:
    print("Pass 1/2")
    d1 = read_all(bus)
    print("Pass 2/2")
    d2 = read_all(bus)
    if d1 != d2:
        raise RuntimeError("Double-read mismatch — check wiring/contacts.")
    print("Double-read OK.")
    return bytes(d1)


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
    print("Writing EEPROM...")
    pages = EEPROM_SIZE // PAGE_SIZE
    for i in range(pages):
        if i % 16 == 0:
            print(f"  page {i}/{pages}")
        start = i * PAGE_SIZE
        write_page(bus, start, data[start : start + PAGE_SIZE])
    print("Write Done!")


def count_diff(a: bytes, b: bytes) -> int:
    return sum(1 for x, y in zip(a, b) if x != y)


def make_empty_from(current: bytes) -> bytes:
    """Keep header/serial; clear usage tables to A5A5 + zeros."""
    if len(current) != EEPROM_SIZE:
        raise ValueError("bad size")
    out = bytearray(EEPROM_SIZE)
    out[0:0x80] = current[0:0x80]
    empty320 = bytes([0xA5, 0xA5]) + bytes(318)
    out[0x80:0x1C0] = empty320
    out[0x1C0:0x300] = empty320
    empty640 = bytes([0xA5, 0xA5]) + bytes(638)
    out[0x300:0x580] = empty640
    out[0x580:0x800] = empty640
    return bytes(out)


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
    if len(raw) == EEPROM_SIZE and b"0x" not in raw[:64]:
        return raw

    text = raw.decode("utf-8", errors="ignore")
    hex_bytes = re.findall(r"0x([0-9A-Fa-f]{2})", text)
    if len(hex_bytes) == EEPROM_SIZE:
        return bytes(int(h, 16) for h in hex_bytes)

    plain = re.findall(r"[0-9A-Fa-f]{2}", text)
    if len(plain) == EEPROM_SIZE and "0x" not in text:
        return bytes(int(h, 16) for h in plain)

    raise ValueError(
        f"Could not parse ROM from {path}: expected {EEPROM_SIZE} bytes "
        f"(binary) or {EEPROM_SIZE} hex values (C array / hex text)."
    )


def save_rom(path: Path, data: bytes, fmt: str = "bin") -> None:
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


def restore_backup(bus: SMBus, backup_path: Path) -> bool:
    print(f"FAILSAFE: restoring {backup_path} ...")
    backup = parse_rom_file(backup_path)
    write_all(bus, backup)
    got = read_twice(bus)
    if got == backup:
        print("FAILSAFE: backup restored OK.")
        return True
    print(f"FAILSAFE: restore VERIFY FAILED — {count_diff(backup, got)} byte(s) differ.")
    return False


def write_verify_or_restore(bus: SMBus, target: bytes, backup_path: Path) -> int:
    """Return 0 OK, 2 restored, 1 fail."""
    try:
        write_all(bus, target)
    except Exception as exc:
        print("Write error:", exc)
        return 2 if restore_backup(bus, backup_path) else 1

    try:
        got = read_twice(bus)
    except Exception as exc:
        print("Verify read error:", exc)
        return 2 if restore_backup(bus, backup_path) else 1

    if got == target:
        return 0

    print(f"Verify mismatch — {count_diff(target, got)} byte(s). Restoring backup.")
    return 2 if restore_backup(bus, backup_path) else 1


def cmd_scan(bus: SMBus) -> int:
    print(f"Scanning I2C for M24C16 0x{BASE_ADDR:02X}..0x{BASE_ADDR + 7:02X}...")
    found = []
    for addr in range(BASE_ADDR, BASE_ADDR + 8):
        try:
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
        print("Partial response — try a dump; recheck SDA/SCL if it fails.")
    return 0


def cmd_dump(bus: SMBus, out: Path | None, fmt: str, twice: bool) -> int:
    data = read_twice(bus) if twice else bytes(read_all(bus))
    print()
    print(format_c_array(data), end="")
    if out:
        save_rom(out, data, fmt)
    else:
        print("\nTip: add -o rom.bin to save.")
    return 0


def cmd_write(bus: SMBus, rom_path: Path, skip_verify: bool) -> int:
    data = parse_rom_file(rom_path)
    write_all(bus, data)
    if skip_verify:
        return 0
    print("\nVerifying...")
    dumped = read_twice(bus)
    if dumped == data:
        print("Verification OK.")
        return 0
    print(f"Verification FAILED — {count_diff(data, dumped)} byte(s) differ.")
    return 1


def cmd_verify(bus: SMBus, rom_path: Path) -> int:
    expected = parse_rom_file(rom_path)
    dumped = read_twice(bus)
    if dumped == expected:
        print("Match — chip contents equal ROM file.")
        return 0
    print(f"Mismatch — {count_diff(expected, dumped)} byte(s).")
    return 1


def cmd_zero_usage(bus: SMBus, backup_path: Path, empty_out: Path | None) -> int:
    print("=== ZERO USAGE (keep serial) ===")
    print("Step 1/3 READ + backup")
    current = read_twice(bus)
    save_rom(backup_path, current, "bin")

    target = make_empty_from(current)
    if current == target:
        print("Already empty layout — nothing to write.")
        return 0

    print(f"Step 2/3 WRITE empty usage ({count_diff(current, target)} byte(s) change)")
    print("Step 3/3 VERIFY")
    rc = write_verify_or_restore(bus, target, backup_path)
    if rc == 0:
        print("OK — usage cleared, header/serial preserved.")
        if empty_out:
            save_rom(empty_out, target, "bin")
        return 0
    if rc == 2:
        print("WRITE FAILED — original data restored from backup.")
        return 2
    print("FAILED — check wiring; backup at", backup_path)
    return 1


def cmd_reset(bus: SMBus, fresh_path: Path, backup_path: Path) -> int:
    print("=== RESET (clone fresh image) ===")
    if not fresh_path.exists():
        print(f"Missing {fresh_path}. Use zero-usage, or dump a new chip first.")
        return 1

    fresh = parse_rom_file(fresh_path)
    print("Step 1/3 READ + backup")
    current = read_twice(bus)
    save_rom(backup_path, current, "bin")

    if current == fresh:
        print("Chip already matches fresh image — nothing to write.")
        return 0

    print(f"Step 2/3 WRITE {fresh_path} ({count_diff(current, fresh)} byte(s) change)")
    print("Step 3/3 VERIFY")
    rc = write_verify_or_restore(bus, fresh, backup_path)
    if rc == 0:
        print("OK — chip matches fresh image.")
        return 0
    if rc == 2:
        print("WRITE FAILED — original data restored from backup.")
        return 2
    print("FAILED — check wiring; backup at", backup_path)
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Feature-complete Canon MC-G02 resetter for Raspberry Pi"
    )
    p.add_argument("-b", "--bus", type=int, default=DEFAULT_BUS, help="I2C bus number")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="Probe I2C for the EEPROM")

    dump = sub.add_parser("dump", help="Read full EEPROM")
    dump.add_argument("-o", "--output", type=Path, help="Output file")
    dump.add_argument("--format", choices=("bin", "c", "hex"), default="bin")
    dump.add_argument(
        "--twice",
        action="store_true",
        help="Double-read and require identical dumps (recommended)",
    )

    write = sub.add_parser("write", help="Write a ROM file (no auto-backup)")
    write.add_argument("-i", "--input", type=Path, required=True)
    write.add_argument("--no-verify", action="store_true")

    verify = sub.add_parser("verify", help="Compare chip to a ROM file")
    verify.add_argument("-i", "--input", type=Path, required=True)

    zero = sub.add_parser(
        "zero-usage",
        help="Clear usage tables, keep serial (recommended reset)",
    )
    zero.add_argument(
        "--backup",
        type=Path,
        default=DEFAULT_BACKUP,
        help=f"Backup path (default: {DEFAULT_BACKUP})",
    )
    zero.add_argument(
        "--save-empty",
        type=Path,
        help="Also save built empty image to this path",
    )

    reset = sub.add_parser("reset", help="Clone a fresh ROM with backup/restore failsafe")
    reset.add_argument("-i", "--input", type=Path, required=True, help="Fresh/empty ROM file")
    reset.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with SMBus(args.bus) as bus:
            if args.cmd == "scan":
                return cmd_scan(bus)
            if args.cmd == "dump":
                return cmd_dump(bus, args.output, args.format, args.twice)
            if args.cmd == "write":
                return cmd_write(bus, args.input, args.no_verify)
            if args.cmd == "verify":
                return cmd_verify(bus, args.input)
            if args.cmd == "zero-usage":
                return cmd_zero_usage(bus, args.backup, args.save_empty)
            if args.cmd == "reset":
                return cmd_reset(bus, args.input, args.backup)
    except PermissionError:
        print(
            "Permission denied opening I2C bus.\n"
            "  Try: sudo python3 mc_g02_resetter.py ...\n"
            "  Or: sudo usermod -aG i2c $USER",
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
