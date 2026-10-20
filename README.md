# Veterinary Anesthesia AR

Repository: [gabrieltaala-eng/PD1](https://github.com/gabrieltaala-eng/PD1).

A web-based **Anesthesia Assessment Simulation System for Veterinary Students**. A full-window webcam sits behind AR-style controls, simulated patient monitoring, and two assessment modes. This is a capstone prototype; interventions, angle targets, and scoring are not clinically validated.

## Groupmates: start here

Read **[Windows installation and run instructions](docs/RUNNING.md)**. The current two-mode assessment requires **both the React frontend and FastAPI backend**, even when using simulated hardware. A webcam, ESP32, RFID reader, and Blender model are optional for testing the workflow.

Clone the project:

```powershell
git clone https://github.com/gabrieltaala-eng/PD1.git Veterinary-Anesthesia-AR
cd Veterinary-Anesthesia-AR
```

`git clone` downloads the source into the named folder; `cd` opens the project root. Then use two PowerShell terminals, each starting at that root.

Terminal 1 — backend:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

This selects the backend, creates its local Python environment, installs dependencies, and starts FastAPI. On later launches, only the last command is needed unless dependencies changed.

Terminal 2 — frontend:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

This selects React, installs the locked dependencies, and starts Vite. Open the printed Local URL, usually `http://127.0.0.1:5173`. Leave both terminals running. Press Ctrl+C in each to stop them. `npm.cmd` avoids PowerShell's `npm.ps1` execution-policy issue.

## Assessment flow

- **Option 1 — Full procedure + scenario:** Patient/baseline → initial anesthesia angle + completion → one complication → RFID drug verification → a new intervention angle + completion → final results.
- **Option 2 — Direct scenario:** Patient/baseline → Start Scenario → RFID drug verification → intervention angle + completion → final results. Only the initial anesthesia injection is skipped; intervention angle assessment is shared by both modes.

**[Updated injection and angle guide](docs/ANGLES_AND_INTERVENTION.md)** explains the shared calibrated/smoothed angle module, separate stage records, live overlay, and mandatory manual completion. Correct RFID now displays **Drug Verified** and unlocks the next step rather than finalizing the assessment. The default placeholder routes support simulated injection exercises; real injection requirements are gated on veterinary approval of an injectable intervention. Configured non-injectable routes do not require a syringe angle.

The three complications are Hypotension (MAP decreases), Hypoventilation (RR decreases / EtCO₂ increases), and Bradycardia (HR decreases). The selected complication stays fixed; incorrect RFID attempts are retained and do not change vital targets. Drug 1, Drug 2, and Drug 3 are placeholder exercise mappings, not actual medications.

**[Two-mode workflow, edge-case tests, API messages, and exact code paths](docs/TWO_MODES.md)** covers the complete implementation. Choose simulated input in Hardware to test valid/invalid angles, correct/incorrect/unknown RFID tags, duplicate events, and disconnection without physical devices.

One of 10 fictional patients is assigned and locked for the current student. **End Assessment** saves that report and prepares a different patient. Browser refresh reconnects to the backend session. Reports are stored locally in `backend/data/assessments.sqlite3` (ignored by Git); a backend restart retains reports and marks unfinished sessions interrupted. One backend worker serves one training station.

## Retained AR interface

- Required full-window webcam with automatic startup, USB/built-in selection, mirror and full-screen controls. Browser camera permission is required; assessment controls stay blocked until the live feed is ready.
- Camera IDs such as `0x001` and `0x002`, active-device indicator, refresh and disconnect handling. These are app labels, not USB hardware IDs.
- Animated simulated ECG, respiratory, pleth, MAP, CO₂, and temperature traces; optional locally generated heartbeat beep.
- Optional wire-connection gate for monitor display. It is separate from injection confirmation and RFID input. See [wire controls](docs/patients-and-wire.md).
- Optional GLB viewer: place `canine.glb` in `frontend/public/models/`; drag to rotate and scroll to zoom. Missing models show a placeholder. Blender sources can go in `AR model/`.

The interface is a screen overlay, not a spatially anchored model on the dummy. Marker/camera calibration, validated sensor transforms, real firmware, and licensed veterinary review remain future integration work. MPU6050 orientations do not prove injection completion. No Electron conversion has been made.

## Validation commands

From `frontend`, `npm.cmd test` runs frontend logic checks; `npm.cmd run build` compiles production assets. `npm.cmd run preview` serves that built frontend locally. From `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"
```

This runs wire, assessment, persistence, and actual HTTP/WebSocket transport tests using temporary records. Physical cameras, sound output, and ESP32 hardware still need manual testing. Source maps and configuration instructions are in [the two-mode guide](docs/TWO_MODES.md#10-code-paths).

## Project layout

```text
Veterinary-Anesthesia-AR/
├── frontend/            # React, webcam, UI and waveforms
├── backend/             # FastAPI, WebSocket, assessment and hardware events
│   ├── config/          # Placeholder scenario / UID / scoring configuration
│   └── data/            # Local generated assessment records (not committed)
├── AR model/            # Blender source/export notes
└── docs/                # Installation, workflow and testing guides
```

Keep `frontend/package-lock.json` and `backend/requirements.txt` in Git. Dependencies, virtual environments, generated builds, local records, and credentials are excluded by `.gitignore`. Each groupmate installs their own environment.
