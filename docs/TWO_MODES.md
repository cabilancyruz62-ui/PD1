# Two-mode assessment: run, test, and integrate

Both modes now require intervention injection after correct drug verification when the configured route is injectable. See [Angles and intervention workflow](ANGLES_AND_INTERVENTION.md) for calibration, stage tokens, route approval, and the shared angle module.

This version extends the existing camera/hand-tracking application. It uses **React + Vite** for the interface and **FastAPI + WebSocket** for the assessment state. Both servers must run for assessment; no physical sensors are required in simulation mode. No Electron code is included.

## 1. Start both servers (Windows PowerShell)

From the project root, in terminal 1:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

`cd` selects the backend. `py -m venv` creates your local Python environment; skip it on later runs if the environment already exists. The pip command installs FastAPI, Uvicorn, and the WebSocket dependency (rerun it after this update). Uvicorn starts the backend on port 8000; leave this terminal running. If `py` is unavailable, use a working `python` command instead to create the environment. Environment activation is unnecessary.

In terminal 2, starting again from the project root:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

`cd` selects React. `npm.cmd ci` installs the locked frontend packages; skip it on later launches unless dependencies changed. `npm.cmd run dev` starts Vite. Open its printed **Local** URL, usually `http://127.0.0.1:5173`. Keep both terminals running. Press Ctrl+C in each to stop the servers.

The main menu has two assessment cards. If they are disabled, check the backend connection. Camera selection, pretrained hand tracking, and the optional GLB viewer remain independent browser features; open Settings to start/select a camera. Camera frames never go to FastAPI.

## 2. Shared setup

1. Choose an assessment card. The patient's biography and baseline simulated vitals become available.
2. Open **Patient Info** and confirm the review acknowledgement.
3. Open **Scenario** and select one of: Hypotension, Hypoventilation, or Bradycardia. This selection locks when the procedure/scenario begins.
4. Open **Hardware**. Keep **SIMULATED** selected for testing without an ESP32. Real hardware can only be selected during baseline preparation.
5. Optionally enable the heartbeat beep in Vitals or Settings. Waveforms continue to respond to simulated values, but there is no auto-cycle between complications and no medication picker.

The assigned patient stays fixed. **End Assessment** closes the report and randomly assigns a different patient for the next student. Changing panels, the scenario selection during preparation, or hardware status never switches patients. Refreshing the browser reconnects to the backend's current assessment rather than restarting it.

## 3. Test Option 1: Full procedure + scenario

1. Choose **Option 1** and select a complication during preparation.
2. Click **Begin Injection**. The Hardware panel opens.
3. Under **Simulation controls**, click **Valid angle · 22°**. The panel should display the synthetic angle, simulated calibration ID, and Within target.
4. Within five seconds, press **Complete Injection**. If the sample expires, press the angle button again. The confirmation requires a fresh calibrated sample taken during this injection step; a sample from before Begin Injection is not sufficient.
5. The one selected complication appears, vital targets change, and the response timer starts after the browser acknowledges displaying it.
6. Open **Assessment → Checklist**, select the observed complication, and press **Record recognition**.
7. Open Hardware and press **Incorrect RFID tag**. A popup shows the detected placeholder drug, active scenario, and incorrect status. The attempt is saved. Both Try Again and Continue Assessment dismiss the popup; Continue opens Assessment. The scenario and vital targets stay unchanged, and another attempt is still possible.
8. Press **Correct RFID tag**. The Drug Verified popup appears and a new intervention injection stage opens. Submit a fresh **Valid angle · 22°** sample, then press **Complete Intervention Injection**. Results become final only after this confirmation.
9. Press **End Assessment**. Check the saved report and next patient's assignment.

Repeat with **Invalid angle · 45°**. A fresh calibrated angle outside the target still allows the explicit injection confirmation; its failed angle criterion is retained and loses the configured angle points. The device orientation itself never confirms administration. Complete Injection without a fresh calibrated angle produces a clear error.

The inclusive 15°–30° rule is a configurable prototype target pending veterinary-expert review. A hardware calibration flag is a device assertion, not proof of clinical validation.

## 4. Test Option 2: Direct scenario

1. Choose **Option 2**.
2. Review the patient, choose a complication, and inspect baseline vitals.
3. Click **Start Scenario**. The complication is displayed immediately.
   The monitor immediately uses the selected scenario targets: Hypotension MAP 50 mmHg; Hypoventilation RR 6/min and EtCO₂ 55 mmHg; Bradycardia HR 45/min. Other channels retain their simulated baseline. Waveforms and the enabled heartbeat beep follow the simulated readings. The affected channels show their scenario targets, and the complication remains during intervention injection and result review until End Assessment.
4. Record recognition, then use the RFID test controls to submit an intervention.
5. A correct tag verifies the drug and opens the intervention angle panel. Submit a fresh angle, then press **Complete Intervention Injection**.
6. View Feedback and End Assessment.

Option 2 skips only the initial injection. Both modes require a new intervention angle and explicit intervention completion for an injectable route. Initial injection actions remain unavailable in Option 2.

## 5. Scenario and RFID configuration

All intervention/score rules live in `backend/config/assessment.json`. Restart the backend after editing this file. Starting or restarting the backend marks unfinished saved assessments interrupted, so finish the current session before changing configuration.

| Scenario | Simulated change | Expected placeholder | Registered test UID |
| --- | --- | --- | --- |
| Hypotension | MAP target decreases | Drug 1 | `RFID_TAG_001` |
| Hypoventilation | RR decreases and EtCO₂ increases | Drug 2 | `RFID_TAG_002` |
| Bradycardia | HR decreases | Drug 3 | `RFID_TAG_003` |

Only the named channels change their targets; other channels retain synthetic baseline variation. The selected complication remains through incorrect attempts. A correct RFID verifies the drug and opens the configured intervention step; manual intervention completion finalizes results. The complication stays visible until End Assessment. No automatic recovery effect is applied.

The UID must match a key in `rfid_registry`; no drug is inferred from a UID suffix or assumed drug number. Replace those placeholder keys with actual reader UIDs when integrating hardware. UID comparisons trim outside whitespace and use uppercase; preserve any byte separators consistently between the registry and firmware.

**Drug 1–3 are not medication recommendations.** Actual drug/intervention rules need licensed veterinary review. Hypoventilation can require airway or ventilation management rather than medication. This prototype checks exercise mappings only and claims no clinical validation.

## 6. Test edge cases

- **Specific/unknown UID:** Type `RFID_TAG_001` or an unregistered value into Hardware's UID box. Unregistered tags produce a distinct popup, remain in the attempt log, and do not identify a drug automatically.
- **Duplicate:** After a scan, click Repeat last event. The replayed event is ignored without adding an attempt or changing the first response time. Repeated same-tag reads with new event IDs within the configured 1.5-second debounce are also ignored. A deliberate retry after that interval is a new attempt.
- **No active scenario:** Submit a test tag during preparation. It is logged as ignored and does not start timing or affect scoring.
- **Disconnect:** Click Disconnect sensors while a complication is active, then scan. The attempt is ignored without scoring. Reconnect sensors and submit a new tag (allow debounce to expire if retrying the same UID).
- **Reader/MPU expiry:** Real ESP32 connection flags expire after five seconds without a status heartbeat. Stale/uncalibrated angles cannot confirm injection. Hardware errors appear in the panel and action feedback.
- **Camera continuity:** Start the camera and open/close every panel and the RFID popup. The video element stays mounted.
- **Browser reconnect:** Reload during an active assessment. It should reconnect to the same patient, mode, scenario, and recorded attempts. A response timer that already started continues on the backend, including time spent away from the page.
- **End early:** End before completing every criterion. The saved report retains the unmet tasks and provisional work as a final ended result; the next student's state starts clean.

## 7. Timing, scoring, and records

The browser acknowledges `scenario_visible` after rendering the scenario banner. The backend starts a monotonic timer on receipt of that acknowledgement. This approximates visible onset with browser/network latency; it is not a calibrated clinical stopwatch. A scan received before the scenario is active is unscored.

The first non-duplicate submitted RFID intervention in an active scenario sets `first_response_seconds`, including an unknown UID. That value never changes on retries. Each later attempt separately records elapsed seconds from the same scenario onset. Recognition and written notes do not submit an RFID intervention or stop its timer.

Initial configurable rubric:

| Mode | Criteria |
| --- | --- |
| Full | Initial angle 15, initial confirmation 15, recognition 15, drug verification 25, intervention angle 20, intervention completion 10 |
| Direct | Recognition 20, drug verification 35, intervention angle 30, intervention completion 15 |

The score is the weighted completion fraction normalized to 100, minus 5 points per incorrect or unregistered active-scenario attempt, clamped to 0–100. Duplicate, disconnected, and pre-scenario reads are excluded. Patient review and notes are logged without points. Recognition must be recorded before correct drug verification. Drug verification is provisional; intervention completion finalizes the response. Non-injectable routes exclude the intervention-angle weight. Real injectable routes without veterinary approval wait for review and cannot complete through angle controls.

FastAPI saves session snapshots to `backend/data/assessments.sqlite3`, excluded from Git. `/api/assessment/results` returns the latest 100 saved records as JSON; Feedback links to it. All rows remain in SQLite even when older than that list limit. A backend restart retains records but marks unfinished sessions interrupted and prepares a new station session; hardware must reconnect/recalibrate. Keep one backend worker per training station. Multiple browser windows connected to that backend share one assessment, not separate students.

## 8. ESP32 event contract (prepared, not physically validated)

Use `POST /api/hardware/events` or WebSocket `/api/ws/hardware`. Browser state streams at `/api/ws/assessment`; the UI also has an HTTP state fallback. The local Vite proxy forwards HTTP and WebSocket requests to FastAPI.

Send status once per second, even if unchanged:

```json
{"type":"status","source":"esp32","device_id":"esp32-station-1","event_id":"boot-A-status-1","esp32_connected":true,"mpu_connected":true,"rfid_connected":true}
```

Before samples, read the active `session_id` and `injection_stage_id` from `GET /api/assessment/state`. Hardware WebSocket welcome/ack messages include both IDs. Refresh them when the stage changes; an initial-injection sample cannot satisfy intervention injection.

```json
{"type":"angle","source":"esp32","device_id":"esp32-station-1","event_id":"boot-A-angle-1","session_id":"COPY_CURRENT_SESSION_ID","injection_stage_id":"COPY_CURRENT_STAGE_ID","angle_deg":22.0,"calibrated":true,"calibration_id":"skin-plane-calibration-1"}
```

A firmware-provided angle must already be relative to the calibrated dummy surface. Alternatively, send both `syringe_quaternion` and `dummy_quaternion` in scalar-last `[x,y,z,w]` order with a registered calibration ID. The shared backend module applies mounting/reference calibration, computes the angle to the surface plane, and smooths it. Raw pitch subtraction and hand landmarks do not supply this angle. Unknown calibration, invalid geometry, stale samples, and replayed events cannot satisfy confirmation. See [Angles and intervention workflow](ANGLES_AND_INTERVENTION.md) for the calibration contract and examples.

```json
{"type":"rfid","source":"esp32","device_id":"esp32-station-1","event_id":"boot-A-scan-1","session_id":"COPY_CURRENT_SESSION_ID","uid":"RFID_TAG_001"}
```

Use a unique event ID for every deliberate physical scan and reuse it on transport retries. Include a boot/session component so rebooting firmware does not reuse old IDs. Register actual UID values rather than assigning tags by read order. RFID scans with no assessment session may omit `session_id`; they are unscored. Source simulation cannot be sent to this real-hardware endpoint; UI simulation commands are separate and carry their own provenance.

```json
{"type":"error","source":"esp32","device_id":"esp32-station-1","event_id":"boot-A-error-1","component":"rfid","message":"RFID reader disconnected"}
```

For Wi-Fi hardware, use the PC's LAN address and deliberately bind the backend to that interface; browser testing can stay on localhost. A USB connection alone is not an event adapter. Firmware, wiring, pin selection, calibration, and physical-reader testing are still future work. These development endpoints have no device authentication; keep them on a trusted isolated demo network and add authentication before deployment. No firmware is flashed by this update.

## 9. Automated checks

From `frontend`:

```powershell
npm.cmd test
npm.cmd run build
```

These run frontend logic checks and compile production assets into `frontend/dist`. From `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"
```

This runs wire, assessment-state, SQLite, HTTP-validation, and live WebSocket tests. Transport tests start a private backend on a temporary local port with a temporary database, then stop it; they do not modify the station's saved records. Browser permissions, rendered camera alignment, audio output, and physical sensors still need hands-on checks.

## 10. Code paths

All paths are relative to the repository root:

| File | Responsibility |
| --- | --- |
| `backend/config/assessment.json` | Scenarios, UID registry, angle target, scoring and freshness settings |
| `backend/assessment_models.py` | Validated command, wire, and ESP32 schemas |
| `backend/assessment.py` | Modes, injection gate, one-scenario lifecycle, RFID matching, timing and scores |
| `backend/angles.py` | Shared calibrated surface-angle geometry and stage-scoped smoothing |
| `backend/test_angles.py`, `backend/test_injection_workflow.py` | Geometry, calibration, both injection stages and route gates |
| `backend/assessment_store.py` | SQLite records and interrupted-session handling |
| `backend/main.py` | REST and WebSocket endpoints |
| `backend/wire.py` | Existing optional wire heartbeat state |
| `backend/requirements.txt` | Python and WebSocket dependencies |
| `backend/test_assessment.py` | Mode, scoring, timing, sensor and persistence tests |
| `backend/test_transports.py` | Real HTTP/WebSocket integration tests with temporary data |
| `backend/test_wire.py`, `backend/test_wire_api.py` | Existing wire tests |
| `frontend/src/hooks/useAssessment.js` | State stream, reconnect, commands and visible-scenario acknowledgement |
| `frontend/src/hooks/useMonitorSound.js` | Retained local heartbeat tone and audio-context recovery |
| `frontend/src/lib/assessmentView.js` | Mode labels, mode-specific checklist and time formatting |
| `frontend/src/lib/monitor.js` | Existing waveform functions and monitor channels |
| `frontend/src/App.jsx` | Persistent camera shell and panel integration |
| `frontend/src/components/ModeSelection.jsx` | Two-mode main menu |
| `frontend/src/components/SimulationControls.jsx` | Procedure/start/end controls |
| `frontend/src/components/ScenarioPanel.jsx` | Scenario preparation, status and instructions |
| `frontend/src/components/HardwarePanel.jsx` | Source selection, status, angle/tag display and test controls |
| `frontend/src/components/InjectionAngle.jsx` | Shared live camera overlay and embedded angle display |
| `frontend/src/components/AssessmentPanel.jsx` | Checklist, scores, attempts and feedback |
| `frontend/src/components/InterventionNotice.jsx` | Correct, incorrect, unknown and sensor notification dialogs |
| `frontend/src/components/MonitorPanel.jsx` | Scenario-driven simulated vital display |
| `frontend/src/components/Waveform.jsx` | Animated traces |
| `frontend/src/style.css` | Mode menu, panel layout and popup styling |
| `frontend/vite.config.js` | HTTP/WebSocket development and preview proxy |
| `frontend/tests/assessment.test.js` | Checklist and monitor view checks |

The previous browser-only simulation reducer and auto-cycling tests were replaced by backend assessment rules and their tests. Existing camera IDs, hand tracking, optional wire gate, monitor beep, and GLB support are retained.

Implementation references: [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) and [Uvicorn WebSocket installation](https://uvicorn.dev/installation/).
