"""
Canon MC-G02 maintenance cartridge EEPROM resetter for Raspberry Pi Pico.

Default MODE="zero_usage" (no fresh cartridge needed):
  1) READ chip twice -> backup.bin
  2) KEEP header/serial (0x000-0x07F)
  3) CLEAR usage tables to empty layout (A5A5 + zeros) with valid checksums
  4) WRITE + verify; on fail restore backup.bin

Also supported:
  MODE="reset"         needs fresh.bin clone
  MODE="capture_fresh" dump a real new chip to fresh.bin

Wiring (10k pull-ups required):
  VCC->3V3  GND->GND  SDA->GP4  SCL->GP5
  10k SDA->3V3  10k SCL->3V3

LED (GP25):
  blink              = ready (waiting for chip)
  solid              = working
  5 short flash, off = done (success)
  2 blink, pause, 2 blink = error
  solid (after error)= restoring backup
  10 fast flash, off = restore done
"""

import time
from machine import Pin, I2C

EEPROM_SIZE = 2048
BASE_ADDR = 0x50
PAGE_SIZE = 16
WRITE_DELAY_MS = 10

SDA_PIN = 4
SCL_PIN = 5
I2C_ID = 0
I2C_FREQ = 100_000
LED_PIN = 25

# "zero_usage"    = clear usage tables, keep serial (no fresh.bin needed)
# "reset"         = write fresh.bin clone (+ restore failsafe)
# "capture_fresh" = dump NEW/empty chip to fresh.bin
# "dump"          = dump current chip to backup.bin only
# "write"         = write fresh.bin only
MODE = "zero_usage"

FRESH_PATH = "fresh.bin"
BACKUP_PATH = "backup.bin"

_i2c = None
_led = None

# Result codes for LED handling
OK = "ok"
ALREADY = "already"
RESTORED = "restored"
FAIL = "fail"


def get_led():
    global _led
    if _led is None:
        _led = Pin(LED_PIN, Pin.OUT)
    return _led


def led_on():
    get_led().on()


def led_off():
    get_led().off()


def led_blink(times, on_ms=80, off_ms=80):
    for _ in range(times):
        led_on()
        time.sleep_ms(on_ms)
        led_off()
        time.sleep_ms(off_ms)


def get_i2c():
    global _i2c
    if _i2c is None:
        _i2c = I2C(
            I2C_ID,
            sda=Pin(SDA_PIN),
            scl=Pin(SCL_PIN),
            freq=I2C_FREQ,
        )
    return _i2c


def i2c_addr_for(offset):
    return BASE_ADDR | (offset >> 8)


def word_addr(offset):
    return offset & 0xFF


def read_byte(offset):
    i2c = get_i2c()
    addr = i2c_addr_for(offset)
    try:
        i2c.writeto(addr, bytes([word_addr(offset)]))
        return i2c.readfrom(addr, 1)[0]
    except OSError as exc:
        raise RuntimeError(
            "I2C read failed at offset %d (dev 0x%02X). Check wiring/pull-ups."
            % (offset, addr)
        ) from exc


def write_page(offset, page):
    if not (1 <= len(page) <= PAGE_SIZE):
        raise ValueError("page length must be 1..16")
    if offset % PAGE_SIZE != 0:
        raise ValueError("offset must be page-aligned")
    i2c = get_i2c()
    addr = i2c_addr_for(offset)
    try:
        i2c.writeto(addr, bytes([word_addr(offset)]) + bytes(page))
    except OSError as exc:
        raise RuntimeError(
            "I2C write failed at offset %d (dev 0x%02X). Check wiring/pull-ups."
            % (offset, addr)
        ) from exc
    time.sleep_ms(WRITE_DELAY_MS)


def read_all():
    data = bytearray(EEPROM_SIZE)
    print("Reading EEPROM...")
    for i in range(EEPROM_SIZE):
        data[i] = read_byte(i)
        if (i + 1) % 256 == 0:
            print("  read %d/%d" % (i + 1, EEPROM_SIZE))
    return data


def read_twice():
    """Failsafe: two identical dumps required."""
    print("Pass 1/2")
    d1 = read_all()
    print("Pass 2/2")
    d2 = read_all()
    if d1 != d2:
        raise RuntimeError("Double-read mismatch — check wiring/contacts.")
    print("Double-read OK.")
    return bytes(d1)


def write_all(data):
    if len(data) != EEPROM_SIZE:
        raise ValueError("ROM must be exactly %d bytes, got %d" % (EEPROM_SIZE, len(data)))
    print("Writing EEPROM...")
    pages = EEPROM_SIZE // PAGE_SIZE
    for i in range(pages):
        if i % 16 == 0:
            print("  page %d/%d" % (i, pages))
        start = i * PAGE_SIZE
        write_page(start, data[start : start + PAGE_SIZE])
    print("Write Done!")


def count_diff(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            n += 1
    return n


def parse_rom_bytes(raw):
    if len(raw) == EEPROM_SIZE:
        if raw[:20].find(b"0x") < 0 and raw[:20].find(b"const") < 0:
            return bytes(raw)

    text = raw.decode("utf-8", "ignore")
    hex_bytes = []
    i = 0
    while i < len(text) - 3:
        if text[i : i + 2] in ("0x", "0X"):
            try:
                hex_bytes.append(int(text[i + 2 : i + 4], 16))
                i += 4
                continue
            except ValueError:
                pass
        i += 1

    if len(hex_bytes) == EEPROM_SIZE:
        return bytes(hex_bytes)
    raise ValueError(
        "Could not parse ROM: need %d bytes (got hex count %d)"
        % (EEPROM_SIZE, len(hex_bytes))
    )


def load_rom(path):
    with open(path, "rb") as f:
        return parse_rom_bytes(f.read())


def save_rom_bin(path, data):
    with open(path, "wb") as f:
        f.write(data)
    print("Saved %d bytes -> %s" % (len(data), path))


def rom_exists(path):
    try:
        with open(path, "rb"):
            return True
    except OSError:
        return False


def chip_present():
    try:
        found = get_i2c().scan()
    except OSError:
        return False
    return any(BASE_ADDR <= a <= BASE_ADDR + 7 for a in found)


def scan():
    print("Scanning I2C for M24C16 (0x50..0x57)...")
    found = get_i2c().scan()
    targets = [a for a in found if BASE_ADDR <= a <= BASE_ADDR + 7]
    if not found:
        print("No I2C devices. Check wiring + 10k pull-ups.")
        return False
    print("Devices:", ["0x%02X" % a for a in found])
    if targets:
        print("EEPROM blocks:", ["0x%02X" % a for a in targets])
        return True
    print("No M24C16-range address.")
    return False


def dump(path=None):
    data = read_twice()
    if path:
        save_rom_bin(path, data)
    return data


def write(path, verify_after=True):
    data = load_rom(path)
    write_all(data)
    if not verify_after:
        return True
    print("Verifying...")
    dumped = read_twice()
    if dumped == data:
        print("Verification OK.")
        return True
    print("Verification FAILED — %d byte(s) differ." % count_diff(data, dumped))
    return False


def verify(path):
    expected = load_rom(path)
    dumped = read_twice()
    if dumped == expected:
        print("Match.")
        return True
    print("Mismatch — %d byte(s)." % count_diff(expected, dumped))
    return False


def _wait_until(present, message, blink=True):
    """blink=True => ready pulse while waiting."""
    print(message)
    while chip_present() != present:
        if blink:
            led_on()
            time.sleep_ms(350)
            led_off()
            time.sleep_ms(350)
        else:
            time.sleep_ms(200)


def _signal_done():
    """Success: 5 short flashes, then off."""
    led_blink(5, on_ms=70, off_ms=70)
    led_off()


def _signal_error():
    """Error: double-blink, pause, double-blink."""
    led_blink(2, on_ms=100, off_ms=100)
    time.sleep_ms(400)
    led_blink(2, on_ms=100, off_ms=100)
    time.sleep_ms(200)


def _signal_restore_done():
    """Restore finished: 10 fast flashes, then off."""
    led_blink(10, on_ms=50, off_ms=50)
    led_off()


def _restore_backup():
    """
    Error LED -> solid while restoring -> 10 flashes if restore OK.
    """
    print("FAILSAFE: error — restoring backup.bin ...")
    _signal_error()
    led_on()  # solid = restoring

    try:
        backup = load_rom(BACKUP_PATH)
        write_all(backup)
        got = read_twice()
    except Exception as exc:
        print("FAILSAFE: restore exception:", exc)
        led_off()
        _signal_error()
        return False

    if got == backup:
        print("FAILSAFE: backup restored OK.")
        _signal_restore_done()
        return True

    print(
        "FAILSAFE: restore VERIFY FAILED — %d byte(s) differ. Chip may be inconsistent."
        % count_diff(backup, got)
    )
    led_off()
    _signal_error()
    return False


def _do_capture_fresh():
    """One-time: save NEW/empty cartridge image as fresh.bin"""
    led_on()
    print("=== CAPTURE FRESH (use a NEW/EMPTY cartridge) ===")
    data = read_twice()
    save_rom_bin(FRESH_PATH, data)
    print("fresh.bin ready. Set MODE='reset' for full cartridges.")
    return OK


def _do_dump_cycle():
    led_on()
    data = read_twice()
    save_rom_bin(BACKUP_PATH, data)
    return OK


def _do_write_cycle():
    led_on()
    if write(FRESH_PATH, verify_after=True):
        return OK
    return FAIL


def make_empty_from(current):
    """
    Build an 'empty' image from a used dump:
      - keep 0x000-0x07F identity/header (serial + checksum)
      - clear usage logs to brand-new layout: 0xA5A5 + zeros
    Each 64/320/640-byte section must sum to 0xA5A5 as LE uint16 words.
    """
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


def _write_verify_or_restore(target):
    try:
        write_all(target)
    except Exception as exc:
        print("Write error:", exc)
        if _restore_backup():
            return RESTORED
        return FAIL

    try:
        got = read_twice()
    except Exception as exc:
        print("Verify read error:", exc)
        if _restore_backup():
            return RESTORED
        return FAIL

    if got == target:
        return OK

    print("Verify mismatch — %d byte(s). Restoring backup." % count_diff(target, got))
    if _restore_backup():
        return RESTORED
    return FAIL


def _do_zero_usage_cycle():
    """Clear usage tables; keep this chip's serial/header."""
    led_on()
    print("=== ZERO USAGE (keep serial) ===")
    print("Step 1/3 READ + backup")
    current = read_twice()
    save_rom_bin(BACKUP_PATH, current)

    target = make_empty_from(current)
    if current == target:
        print("Already empty layout — nothing to write.")
        return ALREADY

    print(
        "Step 2/3 WRITE empty usage tables (%d byte(s) change)"
        % count_diff(current, target)
    )
    print("Step 3/3 VERIFY")
    result = _write_verify_or_restore(target)
    if result == OK:
        print("OK — usage cleared, header/serial preserved.")
        save_rom_bin("empty_built.bin", target)
    return result


def _do_reset_cycle():
    """Clone fresh.bin onto chip with backup failsafe."""
    led_on()
    print("=== RESET FLOW (clone fresh.bin) ===")

    if not rom_exists(FRESH_PATH):
        print("Missing %s — use MODE='zero_usage' or capture_fresh first." % FRESH_PATH)
        return FAIL

    fresh = load_rom(FRESH_PATH)
    if len(fresh) != EEPROM_SIZE:
        print("fresh.bin wrong size.")
        return FAIL

    print("Step 1/3 READ (backup current chip)")
    current = read_twice()
    save_rom_bin(BACKUP_PATH, current)

    if current == fresh:
        print("Chip already matches fresh.bin — nothing to write.")
        return ALREADY

    print("Step 2/3 WRITE fresh.bin (%d byte(s) change)" % count_diff(current, fresh))
    print("Step 3/3 VERIFY")
    result = _write_verify_or_restore(fresh)
    if result == OK:
        print("OK — chip matches fresh.bin.")
    return result


def run_loop(mode=None):
    mode = mode or MODE
    print(
        "MC-G02 mode=%s  LED=GP%d  I2C=SDA GP%d / SCL GP%d"
        % (mode, LED_PIN, SDA_PIN, SCL_PIN)
    )

    if mode in ("reset", "write") and not rom_exists(FRESH_PATH):
        print("ERROR: %s not found." % FRESH_PATH)
        print("Use MODE='zero_usage' (no fresh dump needed), or capture_fresh first.")
        while True:
            _signal_error()
            time.sleep_ms(600)

    handlers = {
        "zero_usage": _do_zero_usage_cycle,
        "reset": _do_reset_cycle,
        "capture_fresh": _do_capture_fresh,
        "dump": _do_dump_cycle,
        "write": _do_write_cycle,
    }
    if mode not in handlers:
        print("Unknown MODE:", mode)
        return

    while True:
        # Blink = ready
        _wait_until(True, "Ready — waiting for chip...", blink=True)
        time.sleep_ms(250)
        if not chip_present():
            continue

        print("Chip detected.")
        # Solid = working (handlers also keep LED on)
        led_on()
        try:
            result = handlers[mode]()
        except Exception as exc:
            print("Exception:", exc)
            result = FAIL

        if result in (OK, ALREADY):
            print("SUCCESS (%s). 5 flashes = done. Unplug chip." % result)
            _signal_done()
            _wait_until(False, "Done — unplug chip.", blink=False)
        elif result == RESTORED:
            # Error + solid restore + 10 flashes already shown in _restore_backup
            print("WRITE FAILED — backup restored (10 flashes). Unplug chip.")
            led_off()
            _wait_until(False, "Restored — unplug chip.", blink=False)
        else:
            print("FAILED. Check wiring / fresh.bin.")
            _signal_error()
            led_off()
            _wait_until(False, "Error — unplug chip.", blink=False)

        led_off()
        time.sleep_ms(300)


if __name__ == "__main__":
    run_loop()
