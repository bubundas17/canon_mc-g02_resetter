/*
 * Canon MC-G02 / MC-G01 — zero_usage reset (feature-complete)
 *
 * Same logic as Pico/Pi:
 *   1) Double-read chip -> backup[] in RAM
 *   2) Keep header/serial (0x000-0x07F)
 *   3) Clear usage tables to A5A5 + zeros (valid checksums)
 *   4) Write + verify; on failure restore backup[]
 *
 * Board RAM: needs ~2.5KB+ free SRAM.
 *   OK: Mega, Uno R4, Leonardo (tight), ESP32, RP2040, STM32, ...
 *   NOT OK: classic Uno / Nano (ATmega328P, 2KB SRAM) — use Pico or Mega.
 *
 * Wiring: VCC, GND, SDA, SCL + 2x 10k pull-ups to VCC.
 * Serial: 115200 baud.
 */

#include <Wire.h>

#if defined(__AVR_ATmega328P__) || defined(__AVR_ATmega168__)
#error "ATmega328P (Uno/Nano) does not have enough RAM for backup[]. Use Mega, Uno R4, ESP32, or the Raspberry Pi Pico MicroPython tool."
#endif

static const uint16_t EEPROM_SIZE = 2048;
static const uint8_t BASE_ADDR = 0x50;
static const uint8_t PAGE_SIZE = 16;
static const uint16_t HEADER_SIZE = 0x80;

static uint8_t backup[EEPROM_SIZE];

static uint8_t i2cAddrFor(uint16_t offset) {
  return (uint8_t)(BASE_ADDR | (offset >> 8));
}

static uint8_t wordAddr(uint16_t offset) {
  return (uint8_t)(offset & 0xFF);
}

static bool eepromReadByte(uint16_t offset, uint8_t *out) {
  uint8_t dev = i2cAddrFor(offset);
  Wire.beginTransmission(dev);
  Wire.write(wordAddr(offset));
  if (Wire.endTransmission() != 0) {
    return false;
  }
  if (Wire.requestFrom((int)dev, 1) != 1) {
    return false;
  }
  *out = (uint8_t)Wire.read();
  return true;
}

static bool eepromWritePage(uint16_t offset, const uint8_t *data, uint8_t length) {
  uint8_t dev = i2cAddrFor(offset);
  Wire.beginTransmission(dev);
  Wire.write(wordAddr(offset));
  for (uint8_t i = 0; i < length; i++) {
    Wire.write(data[i]);
  }
  if (Wire.endTransmission() != 0) {
    return false;
  }
  delay(10);
  return true;
}

static bool readAll(uint8_t *dest) {
  Serial.println(F("Reading EEPROM..."));
  for (uint16_t i = 0; i < EEPROM_SIZE; i++) {
    if (!eepromReadByte(i, &dest[i])) {
      Serial.print(F("Read fail at "));
      Serial.println(i);
      return false;
    }
    if ((i + 1) % 256 == 0) {
      Serial.print(F("  read "));
      Serial.println(i + 1);
    }
  }
  return true;
}

static bool readTwiceToBackup() {
  static uint8_t pass2; // compared streaming against backup after first fill
  Serial.println(F("Pass 1/2"));
  if (!readAll(backup)) {
    return false;
  }
  Serial.println(F("Pass 2/2"));
  for (uint16_t i = 0; i < EEPROM_SIZE; i++) {
    if (!eepromReadByte(i, &pass2)) {
      Serial.print(F("Read fail at "));
      Serial.println(i);
      return false;
    }
    if (pass2 != backup[i]) {
      Serial.print(F("Double-read mismatch at "));
      Serial.println(i);
      return false;
    }
    if ((i + 1) % 256 == 0) {
      Serial.print(F("  check "));
      Serial.println(i + 1);
    }
  }
  Serial.println(F("Double-read OK."));
  return true;
}

/* Expected empty byte at offset, given backup header. */
static uint8_t expectedEmptyByte(uint16_t offset) {
  if (offset < HEADER_SIZE) {
    return backup[offset];
  }
  uint16_t local;
  if (offset < 0x1C0) {
    local = offset - 0x80;
  } else if (offset < 0x300) {
    local = offset - 0x1C0;
  } else if (offset < 0x580) {
    local = offset - 0x300;
  } else {
    local = offset - 0x580;
  }
  if (local < 2) {
    return 0xA5;
  }
  return 0x00;
}

static bool writeEmptyImage() {
  Serial.println(F("Writing empty usage tables..."));
  uint8_t page[PAGE_SIZE];
  uint16_t pages = EEPROM_SIZE / PAGE_SIZE;
  for (uint16_t p = 0; p < pages; p++) {
    if (p % 16 == 0) {
      Serial.print(F("  page "));
      Serial.println(p);
    }
    uint16_t start = p * PAGE_SIZE;
    for (uint8_t j = 0; j < PAGE_SIZE; j++) {
      page[j] = expectedEmptyByte(start + j);
    }
    if (!eepromWritePage(start, page, PAGE_SIZE)) {
      Serial.print(F("Write fail at page "));
      Serial.println(p);
      return false;
    }
  }
  Serial.println(F("Write Done!"));
  return true;
}

static bool verifyEmptyImage() {
  Serial.println(F("Verifying..."));
  uint8_t b;
  uint16_t mismatches = 0;
  for (uint16_t i = 0; i < EEPROM_SIZE; i++) {
    if (!eepromReadByte(i, &b)) {
      Serial.print(F("Verify read fail at "));
      Serial.println(i);
      return false;
    }
    if (b != expectedEmptyByte(i)) {
      mismatches++;
      if (mismatches <= 8) {
        Serial.print(F("  mismatch @0x"));
        Serial.println(i, HEX);
      }
    }
    if ((i + 1) % 256 == 0) {
      Serial.print(F("  verify "));
      Serial.println(i + 1);
    }
  }
  if (mismatches) {
    Serial.print(F("Verify FAILED — "));
    Serial.print(mismatches);
    Serial.println(F(" byte(s) differ."));
    return false;
  }
  Serial.println(F("Verification OK."));
  return true;
}

static bool writeBackupImage() {
  Serial.println(F("FAILSAFE: restoring backup..."));
  uint16_t pages = EEPROM_SIZE / PAGE_SIZE;
  for (uint16_t p = 0; p < pages; p++) {
    if (p % 16 == 0) {
      Serial.print(F("  restore page "));
      Serial.println(p);
    }
    if (!eepromWritePage(p * PAGE_SIZE, &backup[p * PAGE_SIZE], PAGE_SIZE)) {
      Serial.println(F("Restore write failed."));
      return false;
    }
  }
  Serial.println(F("Checking restore..."));
  uint8_t b;
  for (uint16_t i = 0; i < EEPROM_SIZE; i++) {
    if (!eepromReadByte(i, &b) || b != backup[i]) {
      Serial.println(F("Restore VERIFY FAILED."));
      return false;
    }
  }
  Serial.println(F("FAILSAFE: backup restored OK."));
  return true;
}

static bool alreadyEmpty() {
  for (uint16_t i = 0; i < EEPROM_SIZE; i++) {
    if (backup[i] != expectedEmptyByte(i)) {
      return false;
    }
  }
  return true;
}

static void printHeaderPreview() {
  Serial.print(F("Header: "));
  for (uint8_t i = 0; i < 16; i++) {
    if (backup[i] < 16) Serial.print('0');
    Serial.print(backup[i], HEX);
    Serial.print(' ');
  }
  Serial.println();
}

void setup() {
  Wire.begin();
  Serial.begin(115200);
  while (!Serial && millis() < 3000) {
    /* wait for USB serial on native-USB boards */
  }

  Serial.println();
  Serial.println(F("=== MC-G02 zero_usage ==="));
  Serial.println(F("Connect chip, then reset board / reopen serial if needed."));
  delay(500);

  if (!readTwiceToBackup()) {
    Serial.println(F("ERROR: read failed. Check wiring + 10k pull-ups."));
    return;
  }
  printHeaderPreview();

  if (alreadyEmpty()) {
    Serial.println(F("Already empty layout — nothing to write."));
    Serial.println(F("DONE."));
    return;
  }

  if (!writeEmptyImage()) {
    Serial.println(F("ERROR: write failed — attempting restore."));
    writeBackupImage();
    return;
  }

  if (!verifyEmptyImage()) {
    Serial.println(F("ERROR: verify failed — restoring backup."));
    if (writeBackupImage()) {
      Serial.println(F("Restored. Chip left in original state."));
    } else {
      Serial.println(F("CRITICAL: restore failed. Chip may be inconsistent."));
    }
    return;
  }

  Serial.println(F("OK — usage cleared, header/serial preserved."));
  Serial.println(F("DONE. Put chip back in the printer and check level."));
}

void loop() {
}
