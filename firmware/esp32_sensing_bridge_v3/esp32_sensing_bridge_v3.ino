/*
 * ESP32 sensing bridge v3.1 - BENCH TRAINING SIMULATOR ONLY
 *
 * Merges the Madgwick-based needle tracking of esp32_hardware_bridge with the
 * two-sensor, RFID-diagnostic and plunger-volume features of bridge v2.
 *
 * Works with ONE or TWO MPU6050 boards:
 *   - Syringe MPU (0x68, AD0 -> GND): needle elevation above horizontal.
 *   - Dummy MPU   (0x69, AD0 -> 3V3): optional. Measures the forelimb tilt so the
 *     needle angle is reported relative to the forelimb. If it is missing, the
 *     forelimb is ASSUMED LEVEL (dummy_ok=false in the JSON).
 *   The dummy board is probed every 2 s, so it can be connected later.
 *
 * Wiring (classic ESP32, 3.3 V modules only, common GND):
 *   Both MPU  : SDA 21, SCL 22, VCC 3V3
 *   RC522     : SS/SDA->27, SCK->18, MOSI->23, MISO->19, RST->33, 3V3 (on its own VSPI bus)
 *               (the RC522 "SDA" pin is the SPI chip select, NOT I2C SDA)
 *   O2 knob   : end terminals 3V3/GND; wiper GPIO34
 *   Plunger   : slider end terminals 3V3/GND; wiper GPIO35 (optional)
 *   Buzzer    : active buzzer on GPIO25 (set BUZZER_PIN to -1 to disable)
 *
 * Mounting rules:
 *   - Syringe MPU rigid on the syringe; needle axis is learned with 'c'.
 *   - Dummy MPU rigid on the forelimb with its +X axis pointing in the direction the
 *     needle travels when held parallel to the limb. Flip DUMMY_AXIS_SIGN if reversed.
 *
 * Serial commands (one letter, 115200 baud):
 *   h  list commands            z  gyro bias calibration, all sensors still (~2 s)
 *   c  needle-up calibration: hold the NEEDLE STRAIGHT UP (tip up) and still
 *   l  dummy level calibration: lay the forelimb flat on a level surface, still
 *   1,2,3  learn NEXT scanned sticker as glycopyrrolate / ephedrine / anesthesia
 *   x  clear selected drug      p  plunger fully PUSHED (0 mL)
 *   f  plunger fully WITHDRAWN (SYRINGE_CAPACITY_ML)
 *   s  start simulated injection from current plunger position    r  reset injection
 *
 * LIMITATIONS
 *   - Angle = needle elevation minus forelimb elevation. Both come from gravity, so
 *     yaw drift does not affect them, but the result is only valid when the needle
 *     travels in the vertical plane that contains the forelimb axis.
 *   - Quaternion q is the SYRINGE sensor orientation; its yaw drifts (no magnetometer).
 *   - Bench draft: verify angle and volume against reference instruments before using
 *     the numbers as test results.
 *
 * JSON (every 50 ms; lines starting with '#' are status text, not JSON):
 *   angle, elev, drug, scan, o2, volume, q            (fields kept from earlier versions)
 *   dummy_pitch, syringe_pitch, angle_valid, dummy_ok, syringe_ok, rfid_ok,
 *   volume_ready, plunger_ml                          (diagnostics)
 *   uid, scan_seq   last scanned tag UID (any tag, known or not) and a counter that
 *                   increases on every scan; used by backend/serial_bridge.py
 *   cal_ok, cal_id  true after 'c' (needle) is saved and, when the dummy MPU is present,
 *                   'l' (forelimb level) too; cal_id changes whenever either is repeated
 *
 * Library: MFRC522 by miguelbalboa (Library Manager).
 */

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Preferences.h>
#include <math.h>

constexpr uint8_t MPU_SYRINGE_ADDR = 0x68;
constexpr uint8_t MPU_DUMMY_ADDR = 0x69;
constexpr int RFID_SS_PIN = 27;
constexpr int RFID_RST_PIN = 33;
constexpr int RFID_SCK_PIN = 18;
constexpr int RFID_MISO_PIN = 19;
constexpr int RFID_MOSI_PIN = 23;
constexpr int O2_PIN = 34;
constexpr int PLUNGER_PIN = 35;
constexpr int BUZZER_PIN = 25;
// Set to the marked syringe capacity ONLY when the slider spans that full stroke.
constexpr float SYRINGE_CAPACITY_ML = 10.0f;  // EXAMPLE - change for actual syringe
constexpr float DUMMY_AXIS_SIGN = 1.0f;      // -1.0f if dummy +X points against needle travel
constexpr float BETA = 0.1f;                 // Madgwick gain: try 0.03, 0.1, 0.3
constexpr float DEG2RAD_F = 0.0174532925f;
constexpr float RAD2DEG_F = 57.2957795f;

struct Imu {
  uint8_t addr;
  const char *name;
  bool present = false;
  bool sampleOk = false;
  bool idWarned = false;
  uint16_t failCount = 0;
  float q0 = 1, q1 = 0, q2 = 0, q3 = 0;
  float gbx = 0, gby = 0, gbz = 0;       // gyro bias (deg/s)
  float upx = 0, upy = 0, upz = 1;       // gravity "up" in the sensor frame
  unsigned long startMs = 0;
  Imu(uint8_t a, const char *n) : addr(a), name(n) {}
};
Imu syringe(MPU_SYRINGE_ADDR, "Syringe");
Imu dummy(MPU_DUMMY_ADDR, "Dummy");

SPIClass customSPI(VSPI);   // dedicated VSPI bus for the RC522 (as in the tested RFID sketch)
MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
Preferences prefs;
const char *DRUGS[3] = {"glycopyrrolate", "ephedrine", "anesthesia"};
String tagUid[3];
int selectedDrug = 0;   // 0 = none, 1..3 = selected drug
int learnSlot = 0;
unsigned long scanCount = 0;
bool rfidOk = false;
String lastUid;                    // UID of the most recent scan (known or unknown)
unsigned long scanSeq = 0;         // increases on every scan, not on tag registration
bool needleCal = false;            // 'c' saved at least once
bool levelCal = false;             // 'l' saved at least once
unsigned long calSeq = 0;          // increases on every saved 'c' or 'l'

float nax = 1, nay = 0, naz = 0;   // needle axis in syringe sensor frame
float dummyLevelDeg = 0.0f;        // forelimb elevation offset at "level"

float oxygenAdc = 0.0f;
float plungerAdc = 0.0f;
int pushedAdc = -1;
int fullAdc = -1;
bool injectionStarted = false;
float startVolumeMl = 0.0f;

unsigned long lastUs = 0;
unsigned long lastRfidMs = 0;
unsigned long lastPrintMs = 0;
unsigned long lastProbeMs = 0;
unsigned long lastRfidProbeMs = 0;
unsigned long buzzOffMs = 0;

float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
float elevDeg(float s) { return asinf(clampf(s, -1.0f, 1.0f)) * RAD2DEG_F; }

// ---------------------------------------------------------------- buzzer
void beep(unsigned ms) {
  if (BUZZER_PIN < 0) return;
  digitalWrite(BUZZER_PIN, HIGH);
  buzzOffMs = millis() + ms;
}

void serviceBuzzer() {
  if (buzzOffMs != 0 && (long)(millis() - buzzOffMs) >= 0) {
    digitalWrite(BUZZER_PIN, LOW);
    buzzOffMs = 0;
  }
}

// ---------------------------------------------------------------- MPU6050
bool writeRegister(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool readRegister(uint8_t addr, uint8_t reg, uint8_t &value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)addr, 1) != 1) return false;
  value = Wire.read();
  return true;
}

// accel in g (+/-4 g), gyro in deg/s (+/-1000 deg/s)
bool readRaw(uint8_t addr, float &ax, float &ay, float &az,
             float &gx, float &gy, float &gz) {
  Wire.beginTransmission(addr);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)addr, 14) != 14) return false;
  int16_t r[7];
  for (int i = 0; i < 7; i++) {
    uint8_t hi = Wire.read();
    uint8_t lo = Wire.read();
    r[i] = (int16_t)((hi << 8) | lo);
  }
  ax = r[0] / 8192.0f; ay = r[1] / 8192.0f; az = r[2] / 8192.0f;
  gx = r[4] / 32.8f;   gy = r[5] / 32.8f;   gz = r[6] / 32.8f;
  return true;
}

bool beginImu(Imu &m) {
  uint8_t id = 0;
  if (!readRegister(m.addr, 0x75, id)) return false;
  // MPU6050 reports 0x68. Some GY-521 clones report other IDs, so common
  // MPU6500/9250-family IDs are accepted (same register map for these readings).
  if (!(id == 0x68 || (id >= 0x70 && id <= 0x73))) {
    if (!m.idWarned) {
      Serial.printf("# %s MPU: unexpected WHO_AM_I 0x%02X at 0x%02X\n", m.name, id, m.addr);
      m.idWarned = true;
    }
    return false;
  }
  bool ok = writeRegister(m.addr, 0x6B, 0x01) &&   // wake, PLL clock
            writeRegister(m.addr, 0x1A, 0x03) &&   // low-pass filter, about 44 Hz
            writeRegister(m.addr, 0x1B, 0x10) &&   // gyro +/-1000 deg/s
            writeRegister(m.addr, 0x1C, 0x08);     // accel +/-4 g
  if (!ok) return false;
  m.q0 = 1; m.q1 = 0; m.q2 = 0; m.q3 = 0;
  m.failCount = 0;
  m.startMs = millis();
  return true;
}

// Standard Madgwick IMU update (gyro rad/s). Accel is skipped when useAccel is false.
void madgwick(Imu &m, float gx, float gy, float gz,
              float ax, float ay, float az, bool useAccel, float dt, float b) {
  float q0 = m.q0, q1 = m.q1, q2 = m.q2, q3 = m.q3;
  float qd0 = 0.5f * (-q1 * gx - q2 * gy - q3 * gz);
  float qd1 = 0.5f * ( q0 * gx + q2 * gz - q3 * gy);
  float qd2 = 0.5f * ( q0 * gy - q1 * gz + q3 * gx);
  float qd3 = 0.5f * ( q0 * gz + q1 * gy - q2 * gx);

  float n = sqrtf(ax * ax + ay * ay + az * az);
  if (useAccel && n > 0.0f) {
    ax /= n; ay /= n; az /= n;
    float _2q0 = 2 * q0, _2q1 = 2 * q1, _2q2 = 2 * q2, _2q3 = 2 * q3;
    float _4q0 = 4 * q0, _4q1 = 4 * q1, _4q2 = 4 * q2;
    float _8q1 = 8 * q1, _8q2 = 8 * q2;
    float q0q0 = q0 * q0, q1q1 = q1 * q1, q2q2 = q2 * q2, q3q3 = q3 * q3;

    float s0 = _4q0 * q2q2 + _2q2 * ax + _4q0 * q1q1 - _2q1 * ay;
    float s1 = _4q1 * q3q3 - _2q3 * ax + 4 * q0q0 * q1 - _2q0 * ay - _4q1
               + _8q1 * q1q1 + _8q1 * q2q2 + _4q1 * az;
    float s2 = 4 * q0q0 * q2 + _2q0 * ax + _4q2 * q3q3 - _2q3 * ay - _4q2
               + _8q2 * q1q1 + _8q2 * q2q2 + _4q2 * az;
    float s3 = 4 * q1q1 * q3 - _2q1 * ax + 4 * q2q2 * q3 - _2q2 * ay;

    float sn = sqrtf(s0 * s0 + s1 * s1 + s2 * s2 + s3 * s3);
    if (sn > 0.0f) {
      qd0 -= b * s0 / sn;
      qd1 -= b * s1 / sn;
      qd2 -= b * s2 / sn;
      qd3 -= b * s3 / sn;
    }
  }

  q0 += qd0 * dt; q1 += qd1 * dt; q2 += qd2 * dt; q3 += qd3 * dt;
  float qn = sqrtf(q0 * q0 + q1 * q1 + q2 * q2 + q3 * q3);
  if (qn > 0.0f) {
    m.q0 = q0 / qn; m.q1 = q1 / qn; m.q2 = q2 / qn; m.q3 = q3 / qn;
  }
  // "Up" direction in the sensor frame, from the quaternion
  m.upx = 2 * (m.q1 * m.q3 - m.q0 * m.q2);
  m.upy = 2 * (m.q0 * m.q1 + m.q2 * m.q3);
  m.upz = m.q0 * m.q0 - m.q1 * m.q1 - m.q2 * m.q2 + m.q3 * m.q3;
}

void updateImu(Imu &m, float dt) {
  float ax, ay, az, gx, gy, gz;
  if (!readRaw(m.addr, ax, ay, az, gx, gy, gz)) {
    if (m.failCount < 65535) m.failCount++;
    m.sampleOk = m.failCount < 5;       // tolerate brief I2C glitches
    if (m.failCount >= 200) {           // about 1-2 s of failures: treat as unplugged
      m.present = false;
      m.sampleOk = false;
      Serial.printf("# %s MPU lost; probing again every 2 s.\n", m.name);
    }
    return;
  }
  m.failCount = 0;
  m.sampleOk = true;
  float mag = sqrtf(ax * ax + ay * ay + az * az);
  bool useAccel = mag >= 0.8f && mag <= 1.2f;   // ignore gravity under strong motion
  float b = (millis() - m.startMs < 2000) ? 2.0f : BETA;   // fast settle after start
  madgwick(m, (gx - m.gbx) * DEG2RAD_F, (gy - m.gby) * DEG2RAD_F,
           (gz - m.gbz) * DEG2RAD_F, ax, ay, az, useAccel, dt, b);
}

bool settled(const Imu &m) { return m.present && m.sampleOk && millis() - m.startMs >= 1500; }

void calibrateGyros() {
  Imu *list[2] = {&syringe, &dummy};
  if (!syringe.present && !dummy.present) {
    Serial.println("# Gyro calibration skipped: no MPU responding.");
    return;
  }
  Serial.println("# Gyro bias calibration: keep ALL sensors absolutely still...");
  float sum[2][3] = {{0, 0, 0}, {0, 0, 0}};
  int n[2] = {0, 0};
  for (int i = 0; i < 500; i++) {
    for (int k = 0; k < 2; k++) {
      float ax, ay, az, gx, gy, gz;
      if (list[k]->present && readRaw(list[k]->addr, ax, ay, az, gx, gy, gz)) {
        sum[k][0] += gx; sum[k][1] += gy; sum[k][2] += gz; n[k]++;
      }
    }
    delay(4);
  }
  for (int k = 0; k < 2; k++) {
    if (!list[k]->present) continue;
    if (n[k] < 400) {
      Serial.printf("# %s gyro calibration FAILED (too many read errors).\n", list[k]->name);
      continue;
    }
    list[k]->gbx = sum[k][0] / n[k];
    list[k]->gby = sum[k][1] / n[k];
    list[k]->gbz = sum[k][2] / n[k];
    list[k]->startMs = millis();
    Serial.printf("# %s gyro bias (deg/s): %.3f %.3f %.3f\n", list[k]->name,
                  list[k]->gbx, list[k]->gby, list[k]->gbz);
  }
  lastUs = micros();
}

// Needle straight up: the accelerometer direction is the needle axis in the sensor frame.
void calibrateNeedle() {
  if (!syringe.present) {
    Serial.println("# Needle calibration FAILED: syringe MPU not responding.");
    return;
  }
  Serial.println("# Needle calibration: needle straight up (tip up), hold still...");
  float sx = 0, sy = 0, sz = 0;
  int n = 0;
  for (int i = 0; i < 300; i++) {
    float ax, ay, az, gx, gy, gz;
    if (readRaw(syringe.addr, ax, ay, az, gx, gy, gz)) { sx += ax; sy += ay; sz += az; n++; }
    delay(5);
  }
  float m = n > 0 ? sqrtf(sx * sx + sy * sy + sz * sz) / n : 0.0f;
  if (n < 250 || m < 0.9f || m > 1.1f) {
    Serial.println("# Needle calibration FAILED: sensor moved or read errors. Axis unchanged.");
    lastUs = micros();
    return;
  }
  float len = sqrtf(sx * sx + sy * sy + sz * sz);
  nax = sx / len; nay = sy / len; naz = sz / len;
  prefs.putFloat("nx", nax); prefs.putFloat("ny", nay); prefs.putFloat("nz", naz);
  needleCal = true; calSeq++;
  prefs.putBool("nc", true); prefs.putUInt("cs", (uint32_t)calSeq);
  Serial.printf("# Needle axis saved: %.3f %.3f %.3f\n", nax, nay, naz);
  lastUs = micros();
}

// Forelimb flat on a level surface: store its current elevation as the zero reference.
void calibrateDummyLevel() {
  if (!dummy.present) {
    Serial.println("# Level calibration FAILED: dummy MPU not responding.");
    return;
  }
  Serial.println("# Level calibration: forelimb flat and still...");
  float sx = 0, sy = 0, sz = 0;
  int n = 0;
  for (int i = 0; i < 200; i++) {
    float ax, ay, az, gx, gy, gz;
    if (readRaw(dummy.addr, ax, ay, az, gx, gy, gz)) { sx += ax; sy += ay; sz += az; n++; }
    delay(5);
  }
  float len = sqrtf(sx * sx + sy * sy + sz * sz);
  float m = n > 0 ? len / n : 0.0f;
  if (n < 150 || m < 0.9f || m > 1.1f) {
    Serial.println("# Level calibration FAILED: sensor moved or read errors. Offset unchanged.");
    lastUs = micros();
    return;
  }
  dummyLevelDeg = elevDeg(DUMMY_AXIS_SIGN * sx / len);
  prefs.putFloat("dl", dummyLevelDeg);
  levelCal = true; calSeq++;
  prefs.putBool("lc", true); prefs.putUInt("cs", (uint32_t)calSeq);
  Serial.printf("# Dummy level offset saved: %.2f deg\n", dummyLevelDeg);
  lastUs = micros();
}

// ---------------------------------------------------------------- RFID
bool probeRfid() {
  rfid.PCD_Init(RFID_SS_PIN, RFID_RST_PIN);
  delay(30);
  rfid.PCD_SetAntennaGain(MFRC522::RxGain_max);
  uint8_t v = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  bool ok = (v != 0x00 && v != 0xFF);
  if (ok) Serial.printf("# MFRC522 version register: 0x%02X (OK)\n", v);
  else Serial.printf("# MFRC522 version register: 0x%02X - NO COMMUNICATION. Check 3V3, GND, SS->27, SCK->18, MOSI->23, MISO->19, RST->33.\n", v);
  return ok;
}

String uidString() {
  String s;
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 16) s += "0";
    s += String(rfid.uid.uidByte[i], HEX);
  }
  s.toUpperCase();
  return s;
}

// A halted tag is not read again until it leaves the field, so the selected drug stays
// until another tag is scanned (or 'x' is sent). 'scan' counts each recognised scan.
void pollRfid() {
  if (!rfidOk) return;
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  String uid = uidString();
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  if (learnSlot >= 1 && learnSlot <= 3) {
    for (int i = 0; i < 3; i++) {          // one UID per drug slot
      if (i != learnSlot - 1 && tagUid[i] == uid) {
        tagUid[i] = "";
        char otherKey[3] = {'t', (char)('1' + i), 0};
        prefs.putString(otherKey, "");
      }
    }
    tagUid[learnSlot - 1] = uid;
    char key[3] = {'t', (char)('0' + learnSlot), 0};
    prefs.putString(key, uid);
    Serial.printf("# Learned %s = %s\n", DRUGS[learnSlot - 1], uid.c_str());
    learnSlot = 0;
    beep(200);
    return;
  }
  lastUid = uid;      // report every scan so the PC backend decides what the tag means
  scanSeq++;
  for (int i = 0; i < 3; i++) {
    if (tagUid[i].length() > 0 && uid == tagUid[i]) {
      selectedDrug = i + 1;
      scanCount++;
      Serial.printf("# Selected drug: %s\n", DRUGS[i]);
      beep(60);
      return;
    }
  }
  Serial.printf("# Unknown tag %s (send 1, 2 or 3, then scan, to register it)\n", uid.c_str());
  beep(200);
}

// ---------------------------------------------------------------- plunger volume
bool volumeCalibrated() {
  return pushedAdc >= 0 && fullAdc >= 0 && abs(fullAdc - pushedAdc) >= 300;
}

float remainingPlungerMl() {
  float fraction = (plungerAdc - pushedAdc) / (float)(fullAdc - pushedAdc);
  return clampf(fraction, 0.0f, 1.0f) * SYRINGE_CAPACITY_ML;
}

void savePlungerEndpoint(bool pushed) {
  int sampled = 0;
  for (int i = 0; i < 32; i++) { sampled += analogRead(PLUNGER_PIN); delay(3); }
  int value = sampled / 32;
  if (pushed) {
    pushedAdc = value;
    prefs.putInt("v0", value);
    Serial.printf("# Plunger fully PUSHED saved: ADC=%d\n", value);
  } else {
    fullAdc = value;
    prefs.putInt("vf", value);
    Serial.printf("# Plunger fully WITHDRAWN saved: ADC=%d\n", value);
  }
  injectionStarted = false;
  plungerAdc = value;
  if (volumeCalibrated()) Serial.println("# Plunger endpoints valid. Send 's' to start an injection.");
  else Serial.println("# Volume NOT ready: connect the slider and save both endpoints.");
}

// ---------------------------------------------------------------- optional B103 slider diagnostics
// Additive test output only: the existing GPIO35 volume logic and JSON stay intact.
// Send 't' to enable/disable 100 ms readings; send 'n' to reset observed min/max.
constexpr int SLIDER_DIAG_WINDOW = 20;
int sliderDiagHistory[SLIDER_DIAG_WINDOW] = {0};
int sliderDiagCount = 0;
int sliderDiagIndex = 0;
int sliderDiagMin = 4095;
int sliderDiagMax = 0;
bool sliderDiagnosticsEnabled = false; // off by default to avoid extra serial traffic
unsigned long lastSliderDiagMs = 0;

// Sixteen samples averaged without delay, so the IMU update loop is not held up.
int sliderReadAveraged() {
  long sum = 0;
  for (int i = 0; i < 16; ++i) sum += analogRead(PLUNGER_PIN);
  return (int)(sum / 16);
}

void sliderResetDiagnostics() {
  sliderDiagMin = 4095;
  sliderDiagMax = 0;
  sliderDiagCount = 0;
  sliderDiagIndex = 0;
  Serial.println("# Slider observed min/max and noise history reset.");
}

void sliderDiagnosticCommand(char command) {
  if (command == 't') {
    sliderDiagnosticsEnabled = !sliderDiagnosticsEnabled;
    Serial.printf("# Slider diagnostics %s (100 ms).\n",
                  sliderDiagnosticsEnabled ? "ON" : "OFF");
  } else if (command == 'n') {
    sliderResetDiagnostics();
  }
}

void sliderDiagnosticsTick() {
  unsigned long now = millis();
  if (now - lastSliderDiagMs < 100) return;
  lastSliderDiagMs = now;

  // Record the observed span even while diagnostic printing is off.
  int raw = sliderReadAveraged();
  if (raw < sliderDiagMin) sliderDiagMin = raw;
  if (raw > sliderDiagMax) sliderDiagMax = raw;
  sliderDiagHistory[sliderDiagIndex] = raw;
  sliderDiagIndex = (sliderDiagIndex + 1) % SLIDER_DIAG_WINDOW;
  if (sliderDiagCount < SLIDER_DIAG_WINDOW) sliderDiagCount++;

  if (!sliderDiagnosticsEnabled) return;

  int lo = sliderDiagHistory[0];
  int hi = lo;
  for (int i = 1; i < sliderDiagCount; ++i) {
    if (sliderDiagHistory[i] < lo) lo = sliderDiagHistory[i];
    if (sliderDiagHistory[i] > hi) hi = sliderDiagHistory[i];
  }

  bool calibrated = volumeCalibrated();
  float position = 0.0f;
  if (calibrated) {
    position = (raw - pushedAdc) / (float)(fullAdc - pushedAdc);
  } else if (sliderDiagMax > sliderDiagMin) {
    position = (raw - sliderDiagMin) / (float)(sliderDiagMax - sliderDiagMin);
  }
  position = clampf(position, 0.0f, 1.0f);

  // '#' prefix separates test diagnostics from machine-readable JSON lines.
  Serial.printf("# Slider raw=%4d mV~%4ld pos=%5.1f%%",
                raw, (long)raw * 3300L / 4095L, position * 100.0f);
  if (calibrated) Serial.printf(" mL=%.2f", position * SYRINGE_CAPACITY_ML);
  else Serial.print(" mL=--");
  Serial.printf(" noise=%d min=%d max=%d span=%d",
                hi - lo, sliderDiagMin, sliderDiagMax, sliderDiagMax - sliderDiagMin);
  if (raw < 100 || raw > 3995) Serial.print(" [near ADC limit]");
  if (pushedAdc >= 0 && fullAdc >= 0 && !calibrated)
    Serial.print(" [p and f too close: span < 300]");
  Serial.println();
}

// ---------------------------------------------------------------- commands
void printHelp() {
  Serial.println("# Commands: z gyro bias | c needle-up | l dummy level | 1/2/3 learn tag | x clear drug");
  Serial.println("#           p plunger pushed | f plunger withdrawn | s start injection | r reset | h help");
  Serial.println("#           t slider diagnostics ON/OFF | n reset slider observed min/max");
}

void handleCommand(char c) {
  sliderDiagnosticCommand(c);  // Added diagnostics only; existing commands unchanged.
  if (c == 'z') calibrateGyros();
  else if (c == 'c') calibrateNeedle();
  else if (c == 'l') calibrateDummyLevel();
  else if (c == '1' || c == '2' || c == '3') {
    learnSlot = c - '0';
    Serial.printf("# Scan the sticker for %s now...\n", DRUGS[learnSlot - 1]);
  } else if (c == 'x') {
    selectedDrug = 0;
    Serial.println("# Drug selection cleared.");
  } else if (c == 'p' || c == 'f') savePlungerEndpoint(c == 'p');
  else if (c == 's') {
    if (!volumeCalibrated()) {
      Serial.println("# Cannot start injection: plunger not calibrated.");
      return;
    }
    plungerAdc = analogRead(PLUNGER_PIN);
    startVolumeMl = remainingPlungerMl();
    injectionStarted = true;
    Serial.printf("# Simulated injection started at %.2f mL remaining.\n", startVolumeMl);
  } else if (c == 'r') {
    injectionStarted = false;
    Serial.println("# Injection session reset.");
  } else if (c == 'h') printHelp();
}

// ---------------------------------------------------------------- output
void putNum(const char *key, bool ok, float v, uint8_t decimals) {
  Serial.print(",\""); Serial.print(key); Serial.print("\":");
  if (ok) Serial.print(v, decimals); else Serial.print("null");
}

void putBool(const char *key, bool v) {
  Serial.print(",\""); Serial.print(key); Serial.print("\":");
  Serial.print(v ? "true" : "false");
}

void printJson() {
  bool synOk = settled(syringe);
  bool dumOk = settled(dummy);
  float eS = synOk ? elevDeg(nax * syringe.upx + nay * syringe.upy + naz * syringe.upz) : 0.0f;
  float eD = dumOk ? elevDeg(DUMMY_AXIS_SIGN * dummy.upx) - dummyLevelDeg : 0.0f;
  // If the dummy is absent the forelimb is assumed level (eD = 0).
  bool valid = synOk && (dumOk || !dummy.present);
  float elev = eS - eD;   // tip pointing into the forelimb surface is negative
  bool vCal = volumeCalibrated();

  Serial.print("{\"angle\":");
  if (valid) Serial.print(fabsf(elev), 2); else Serial.print("null");
  putNum("elev", valid, elev, 2);
  Serial.print(",\"drug\":");
  if (selectedDrug) { Serial.print('"'); Serial.print(DRUGS[selectedDrug - 1]); Serial.print('"'); }
  else Serial.print("null");
  Serial.printf(",\"scan\":%lu,\"o2\":%.0f", scanCount,
                clampf(oxygenAdc / 4095.0f * 100.0f, 0.0f, 100.0f));
  putNum("volume", vCal && injectionStarted,
         clampf(startVolumeMl - remainingPlungerMl(), 0.0f, SYRINGE_CAPACITY_ML), 2);
  Serial.print(",\"q\":");
  if (synOk) Serial.printf("[%.4f,%.4f,%.4f,%.4f]", syringe.q0, syringe.q1, syringe.q2, syringe.q3);
  else Serial.print("null");
  putNum("dummy_pitch", dumOk, eD, 2);
  putNum("syringe_pitch", synOk, eS, 2);
  putBool("angle_valid", valid);
  putBool("dummy_ok", dumOk);
  putBool("syringe_ok", synOk);
  putBool("rfid_ok", rfidOk);
  putBool("volume_ready", vCal);
  putNum("plunger_ml", vCal, remainingPlungerMl(), 2);
  Serial.print(",\"uid\":");
  if (scanSeq > 0) { Serial.print('"'); Serial.print(lastUid); Serial.print('"'); }
  else Serial.print("null");
  Serial.printf(",\"scan_seq\":%lu", scanSeq);
  putBool("cal_ok", needleCal && (levelCal || !dummy.present));   // level cal is not required without a dummy MPU
  Serial.printf(",\"cal_id\":\"fw-%lu\"", calSeq);
  Serial.println("}");
}

// ---------------------------------------------------------------- setup / loop
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("# Bridge v3 boot (training simulator only). Send 'h' for commands.");
  if (BUZZER_PIN >= 0) { pinMode(BUZZER_PIN, OUTPUT); digitalWrite(BUZZER_PIN, LOW); }

  prefs.begin("needle", false);   // same namespace and keys as earlier versions
  nax = prefs.getFloat("nx", 1.0f);
  nay = prefs.getFloat("ny", 0.0f);
  naz = prefs.getFloat("nz", 0.0f);
  dummyLevelDeg = prefs.getFloat("dl", 0.0f);
  needleCal = prefs.getBool("nc", false);
  levelCal = prefs.getBool("lc", false);
  calSeq = prefs.getUInt("cs", 0);
  pushedAdc = prefs.getInt("v0", -1);
  fullAdc = prefs.getInt("vf", -1);
  tagUid[0] = prefs.getString("t1", "");
  tagUid[1] = prefs.getString("t2", "");
  tagUid[2] = prefs.getString("t3", "");
  Serial.printf("# Needle axis: %.3f %.3f %.3f | dummy level offset: %.2f deg\n",
                nax, nay, naz, dummyLevelDeg);

  Wire.begin(21, 22);
  Wire.setClock(400000);
  syringe.present = beginImu(syringe);
  dummy.present = beginImu(dummy);
  Serial.printf("# Syringe MPU 0x68: %s | Dummy MPU 0x69: %s%s\n",
                syringe.present ? "OK" : "MISSING", dummy.present ? "OK" : "MISSING",
                dummy.present ? "" : " (forelimb assumed level)");

  // RC522 start-up sequence copied from the tested RFID sketch: start VSPI on the RC522
  // pins, wait, init, then make the global SPI object the same bus the library uses.
  customSPI.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, RFID_SS_PIN);
  delay(100);
  rfid.PCD_Init(RFID_SS_PIN, RFID_RST_PIN);
  SPI = customSPI;
  rfidOk = probeRfid();   // repeats the init on the working bus, sets antenna gain, checks version

  analogReadResolution(12);
  oxygenAdc = analogRead(O2_PIN);
  plungerAdc = analogRead(PLUNGER_PIN);
  Serial.printf("# Plunger slider %s\n", volumeCalibrated() ? "CALIBRATED" : "NOT CALIBRATED");

  delay(100);
  calibrateGyros();   // keep sensors motionless at boot; repeat 'z' if moved
  lastUs = micros();
  lastPrintMs = lastRfidMs = lastProbeMs = lastRfidProbeMs = millis();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c != '\n' && c != '\r') handleCommand(c);
  }

  unsigned long nowUs = micros();
  float dt = (nowUs - lastUs) * 1.0e-6f;
  lastUs = nowUs;
  if (dt <= 0.0f || dt > 0.1f) dt = 0.01f;

  if (syringe.present) updateImu(syringe, dt);
  if (dummy.present) updateImu(dummy, dt);

  oxygenAdc = 0.85f * oxygenAdc + 0.15f * analogRead(O2_PIN);
  plungerAdc = 0.85f * plungerAdc + 0.15f * analogRead(PLUNGER_PIN);
  sliderDiagnosticsTick(); // Additive test sampling; original volume logic remains unchanged.

  unsigned long nowMs = millis();
  if (nowMs - lastProbeMs >= 2000) {   // allow sensors to be connected after boot
    lastProbeMs = nowMs;
    if (!syringe.present && beginImu(syringe)) {
      syringe.present = true;
      Serial.println("# Syringe MPU detected. Send 'z' (still) and 'c' (needle up).");
    }
    if (!dummy.present && beginImu(dummy)) {
      dummy.present = true;
      Serial.println("# Dummy MPU detected. Send 'z' (still) and 'l' (forelimb level).");
    }
  }
  if (!rfidOk && nowMs - lastRfidProbeMs >= 5000) {
    lastRfidProbeMs = nowMs;
    rfidOk = probeRfid();
  }
  if (nowMs - lastRfidMs >= 100) {   // poll the tag reader at 10 Hz
    lastRfidMs = nowMs;
    pollRfid();
  }
  if (nowMs - lastPrintMs >= 50) {   // 20 Hz output
    lastPrintMs = nowMs;
    printJson();
  }
  serviceBuzzer();
  delay(10);
}
