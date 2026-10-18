# Assigned patients and optional wire-triggered monitor

## Assigned patients

One of 10 fictional canine profiles is assigned by FastAPI. Choose an assessment mode to view it. There is no patient selector. Patient information stays fixed until **End Assessment**, which saves the completed report and prepares a different patient for the next student.

The browser reconnects to the same running backend assessment after a page refresh. Backend restart marks unfinished records interrupted and creates a new station session; saved records remain in `backend/data/assessments.sqlite3`. See [the two-mode guide](TWO_MODES.md).

## Wire gate: test without hardware

1. Start both servers and choose an assessment mode. Baseline simulated vitals are available.
2. Open **Vitals → Optional wire activation settings**, or the same controls in Settings.
3. **Require wire connection for vitals** is off by default. Leave it off for initial two-mode tests.
4. Enable it, keeping **Simulated wire** as the source.
5. Toggle **Simulate wire connected** on to show the monitor; toggle it off to pause traces, values, and beeps.
6. Disable the requirement to bypass it again.

The wire gate is a browser display control, separate from the Hardware panel's angle/RFID input source. It does not confirm injection, select a drug, change the patient, or measure physiology. It does not pause or reset an active backend response timer. End Assessment resets the simulated wire switch. A browser reload resets these display preferences while reconnecting to the backend assessment.

## ESP32 wire input for later

Select ESP32 hardware as the **wire signal source** when a physical continuity detector is available. The existing endpoint accepts:

```http
POST /api/hardware/wire
Content-Type: application/json

{"connected": true}
```

Send JSON `false` on disconnection. Send the current debounced state every second, including when unchanged. Strings, integers, nulls, and unknown fields are rejected. The backend reports wire freshness under `wire` in `/api/assessment/state`, the assessment WebSocket stream, and `/api/sensors`.

Before the first heartbeat or after five seconds without one, the wire is unknown (`connected:null`, `fresh:false`). The UI also rejects a state response older than three seconds and pauses the monitor when backend communication is unavailable. Simulated wire state cannot satisfy the ESP32 wire source.

No board pin is assumed. A passive contact input needs a suitable board-specific GPIO configuration and debounce. Confirm the board and wiring before implementing firmware; powered clinical leads are not a direct ESP32 input. Connecting USB alone does not deliver this event. Network events and a serial adapter would be separate integrations.

Real MPU6050 and RFID messages use `/api/hardware/events` or `/api/ws/hardware`, not this wire endpoint. The [hardware event contract](TWO_MODES.md#8-esp32-event-contract-prepared-not-physically-validated) includes calibration IDs, current session IDs, registered RFID UIDs, status heartbeats, and sensor errors.

The development backend has no device authentication. Keep LAN tests on a trusted isolated network. Actual firmware, calibration, and licensed veterinary review are still required before using real hardware for grading.
