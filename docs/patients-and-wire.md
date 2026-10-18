# Patient selection and optional wire-triggered vitals

## Try it now without an ESP32

1. Start the frontend as described in the main README (`npm.cmd run dev` from `frontend`).
2. Press **Start Simulation**. Open **Patient Info** to review the assigned patient. There is no patient picker. **End Simulation** is the only in-app action that assigns a different patient, ready for the next student; it also clears the next student's checklist and drafts. See [simulation instructions](SIMULATION.md).
3. Open **Vitals → Wire activation settings** or **Settings → Vitals activation**. The same wire controls appear in both places.
4. **Require wire connection for vitals** is off by default. Sample vitals display normally.
5. Turn it on. **Simulated wire** is selected by default; the monitor shows dashes until **Simulate wire connected** is on.
6. Turn **Simulate wire connected** on to initialize the sample monitor. Turn it off to pause the monitor and remove waveform illustrations.
7. Turn **Require wire connection for vitals** off to bypass the wire requirement again.

Physiological readings now vary with a synthetic demo timeline, patient baseline, and manual sliders. Connecting a wire is an activation trigger, not a measurement of heart rate or other physiology. Vitals also require a running simulation. Disconnecting the wire pauses monitor progression, waveforms, and beeps; reconnecting resumes the same patient's session. Ending a simulation resets the simulated wire to disconnected for the next student. Hardware wire state remains physical state. Session data resets on page reload.

## ESP32 option for later

Choose **ESP32 hardware** as the wire source. Simulated wire state cannot activate hardware mode. A running backend and fresh hardware messages are required. No GPIO pin is assumed and no firmware is flashed by this change.

The backend accepts a debounced boolean input at:

```http
POST /api/hardware/wire
Content-Type: application/json

{"connected": true}
```

Send `false` when the wire is disconnected. Firmware must send the current state every second, even when unchanged, so a lost connection can be distinguished from a connected wire. Send JSON booleans, not strings or integers. Unknown fields are rejected. The backend returns the wire's source, connection state, freshness, age, and timeout. `GET /api/sensors` includes the same object under `wire`.

Before the first message, or after five seconds without a heartbeat, the backend reports `connected: null` and `fresh: false`. The browser polls once per second, clears the signal on API failure, and also expires its last successful response after three seconds. Dashes and a waiting/paused message replace readings when the signal is unavailable. This is intended for a single ESP32 and one backend worker; the current in-memory state is reset on server restart.

The wire gate runs in each browser; backend ingestion continues even if that browser turns the feature off. A connected ESP32 still starts **simulated** vitals, not measured physiology.

Use the normal loopback-only backend for browser-only testing. Later, Wi-Fi ESP32 firmware needs your computer's LAN address, both devices on the same network, and a backend listening on that interface. This development endpoint has no authentication; keep it on a trusted isolated training network and add device authentication before deployment. A USB serial connection would require a separate serial-to-backend adapter; plugging in USB alone does not report wire state.

Confirm the board and suitable input pin before writing firmware. A passive jumper/continuity detector can use a supported `INPUT_PULLUP` input and ground, with debounce and LOW meaning connected. GPIO capabilities differ by ESP32 board; see [Espressif's GPIO documentation](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/gpio.html). Do not connect a powered clinical lead or external voltage directly to an ESP32 input.

## Tests and files

From `frontend`, run `npm.cmd test` to check the 10 profiles, non-repeating random selection, bypass mode, simulated input, and missing/stale hardware handling. Run `npm.cmd run build` to compile the interface.

From `backend`, run `python -m unittest test_wire.py` with a Python interpreter to check initial unknown state, connect/disconnect, timeout, and heartbeat refresh. Run `python -m unittest test_wire_api.py` after installing the backend requirements to check request validation and endpoint responses.

Changed/added code paths, relative to the project root:

- `frontend/src/data/patients.js`: ten fictional profiles and random selection.
- `frontend/src/lib/vitals.js`: sample values and wire-gating rules.
- `frontend/src/components/VitalsControls.jsx`: shared activation/source/test controls.
- `frontend/src/App.jsx`: patient selection, monitor rendering, freshness checks, and backend polling.
- `frontend/src/style.css`: monitor and settings styling.
- `frontend/tests/vitals.test.js`: frontend logic tests.
- `frontend/package.json`: `npm.cmd test` command.
- `backend/wire.py`: thread-safe heartbeat state and expiry.
- `backend/main.py`: ESP32 endpoint and wire field in sensor responses.
- `backend/test_wire.py`: heartbeat tests.
- `backend/test_wire_api.py`: input validation and endpoint tests.
