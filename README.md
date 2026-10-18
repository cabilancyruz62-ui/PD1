# Veterinary Anesthesia AR

Repository: [gabrieltaala-eng/PD1](https://github.com/gabrieltaala-eng/PD1).

## For groupmates: start here

See **[How to run the project on Windows](docs/RUNNING.md)** for GitHub clone / Download ZIP instructions, software requirements, camera setup, optional backend startup, tests, and troubleshooting.

After downloading and opening the project root, the frontend quick start is:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

`cd frontend` opens the React app, `npm.cmd ci` installs the committed dependency versions, and `npm.cmd run dev` starts the local server. Open the Local URL printed in the terminal. Python and an ESP32 are optional for trying the camera, patients, hand tracking, and simulated wire controls.

---

**New:** Each student gets a fixed, randomly assigned patient. **End Simulation** saves that student's in-memory feedback and checklist, then assigns a different patient for the next student. Vitals now change with illustrative animated waveforms and an optional heartbeat beep. See [simulation and assessment instructions](docs/SIMULATION.md) and [wire controls](docs/patients-and-wire.md).

A local web prototype for the **Anesthesia Assessment Simulation System for Veterinary Students**. React and Vite render controls over a full-window webcam feed. Camera frames stay in the browser. The optional FastAPI starter reports unavailable hardware as `null`.

## Current development stages

1. **Phase 1 — setup:** Existing frontend dependencies installed and baseline production build verified before camera changes. JavaScript, React 18, Vite, MediaPipe, Three.js, and Lucide icons are installed; `package-lock.json` records exact versions.
2. **Phase 2 — camera:** Full-window video, start/stop, explicit USB-camera selection, permission errors, device-list changes, disconnected-stream handling, mirror control, and full-screen control.
3. **Phase 3 — panels:** Collapsible Patient Info, Vitals, Settings, Tracking, 3D Patient, and Assessment panels. Opening panels does not remount the video. Each student is assigned one of 10 fictional patients; the assignment changes only after ending the simulation. Dynamic vital readings and waveforms are explicitly simulated.
4. **Phase 4 — tracking foundation:** MediaPipe detection runs in a worker, up to two hands / 21 landmarks each. Frames are processed at a maximum of approximately 15 detections per second, one in flight at a time. The camera continues independently. Matching `object-fit: cover`, centering, and mirroring keep the landmark canvas aligned during resizing. Real camera testing is still required.

The starter Three.js GLB viewer is preserved, with orbit/zoom controls, resize handling, first-clip animation playback, and a missing-model placeholder. It is lazy-loaded when opened.

**Remaining phases:** modular FastAPI services and WebSockets (5), validated hardware ingestion and separately labeled sensor simulation (6), React Three Fiber and marker/calibration anchoring (7), reviewed anesthesia rules and assessment scoring (8). Electron (9) is intentionally deferred. The existing backend is a REST placeholder, not a completed hardware or simulation service.

## Run and test Phase 1 (Windows 10 / 11)

Install Node.js LTS including npm. Open PowerShell and run:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
npm.cmd run dev
```

- `cd` selects this project's frontend folder.
- `npm.cmd install` downloads the dependencies from `package.json`. On later clean installs, `npm.cmd ci` installs the exact lockfile versions.
- `npm.cmd run build` checks compilation and writes production output into `frontend/dist/`.
- `npm.cmd run dev` starts Vite. Open the localhost URL printed in the terminal, normally `http://127.0.0.1:5173`. Keep the terminal open; press Ctrl+C to stop it. Using `npm.cmd` avoids PowerShell restrictions on `npm.ps1`.

Setup test: the interface should appear even with no camera, hardware, model, or backend. A backend-offline status is expected when Python is not running.

## Run and test Phase 2 (camera)

With the development server running:

1. Press **Start Camera** and allow browser permission. Camera names may only become visible after permission is granted.
2. Open **Settings**, select the external USB webcam, and press **Apply / Restart**. Selecting a camera alone does not switch it.
3. Move something in view and confirm the video fills the entire browser background.
4. Open every navigation panel. Confirm the video continues.
5. Toggle mirroring and use the full-screen button. Escape exits full screen.
6. Stop the camera and confirm it stops streaming. Start it again.
7. Unplug an active USB camera and check for a disconnect message. Reconnect, refresh the camera list, and start again.
8. Deny camera permission and confirm a useful error appears. Restore permission through browser site settings to retry.

Camera access needs localhost or HTTPS. Opening `index.html` directly or accessing an insecure LAN IP will not provide a secure camera context. If access fails, close other applications using the webcam. The app requests no audio.

## Run and test Phase 3 (AR interface)

Use the same development server. Open **Patient Info**, **Vitals**, **Settings**, and **Assessment**; click the active tab or panel X to collapse it. The eye button hides and restores AR panels and the skeleton while retaining the camera. Navigation remains available so overlays can always be restored.

Press **Start Simulation**, then resize the window, test a narrow layout, and use Tab to navigate controls. Vitals and waveforms vary with scripted demo conditions and sliders; an optional beep follows simulated HR. Assessment Checklist shows remaining tasks; Feedback records app actions and unfinished tasks. **End Simulation** closes that student's report and assigns a different patient. No clinical score or dose recommendation is generated. Session data and reports are in memory only and reset on reload. See [the complete simulation guide](docs/SIMULATION.md).

## Run and test Phase 4 foundation (hands)

Start the camera and enable **Hand skeleton overlay** in Tracking or Settings. Internet is needed to load the MediaPipe model and matching WASM from Google / jsDelivr. The installed package version determines the WASM URL. Show one hand, then two hands. Status should change between searching and the number detected. Check finger/wrist alignment near all four camera edges, after resizing, and after mirroring. Disable tracking to clear the canvas. A visible message reports worker/model failures.

Detection runs on a worker to keep synchronous inference off the interface thread; actual performance depends on the device. Camera frames are transferred only to that browser worker, never to FastAPI. Hand landmarks do not establish needle angle, volume, contact, or clinical competence.

## Optional existing backend

Python 3.10+ is needed only for this section. In a second PowerShell terminal:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- `cd` selects the backend folder.
- `py -m venv .venv` creates an isolated Python environment.
- The pip command installs the FastAPI dependencies into that environment.
- The uvicorn command starts the API on port 8000 and reloads Python edits. Explicitly using the environment's Python avoids PowerShell activation restrictions.

Visit `http://127.0.0.1:8000/docs` to test `/api/health`, `/api/sensors`, and the new `/api/hardware/wire` input. Vite proxies `/api` to this backend during development and preview. With the backend running, the frontend should show Backend online / Awaiting angle/volume hardware. Disconnected angle/volume values remain unavailable. Stopping Python should return the UI to Backend offline without affecting video. The frontend currently polls REST; WebSocket streaming is a future phase.

To test the built frontend instead of the development server:

```powershell
npm.cmd run preview
```

Run this from `frontend` after a successful build. It serves `dist` locally at the printed URL. This is a local preview, not a production deployment.

## Blender model

Export a GLB to `frontend/public/models/canine.glb`, then open **3D Patient**. Without it a placeholder appears and the rest of the app works. Drag to rotate and scroll to zoom; the first exported animation plays automatically. If the file changes while the panel is open, close and reopen it. Blender sources and exports can be kept in `AR model/`.

This is a screen overlay and separate model viewer, not spatially registered AR. Phase 7 must establish camera intrinsics/distortion, marker dimensions, marker-to-dummy pose, and model transforms before the dog or other graphics can be anchored to the physical dummy.

## Hardware and assessment boundaries

Future hardware messages must distinguish simulation from hardware, carry timestamps and calibration IDs, report freshness/units, and reject invalid or non-finite values. Two MPU6050 sensors need calibrated sensor-to-syringe and sensor-to-skin-plane transforms; raw Euler pitch subtraction does not measure needle insertion relative to skin. The proposed 15–30 degree prototype target needs veterinary-expert validation before use in scoring. Fluid-volume readings need calibration, zero/tare, bounds, and reset behavior. Do not assess students from uncalibrated or stale measurements.

No clinical validation is claimed. Drug effects, complication scenarios, target volumes, response-time rules, and scoring remain future reviewed work.

## Source files (exact relative paths)

All paths below are relative to the project root (the folder containing this README). Commands beginning with `cd frontend` or `cd backend` assume you start at that root in a new terminal:

| Path | Purpose |
| --- | --- |
| `frontend/package.json` | Frontend dependencies and npm commands |
| `frontend/package-lock.json` | Installed dependency versions |
| `frontend/index.html` | Browser entry page |
| `frontend/vite.config.js` | React plugin, local API proxy, MediaPipe version constant |
| `frontend/src/main.jsx` | React entry point |
| `frontend/src/App.jsx` | AR workspace, panels, and optional backend status |
| `frontend/src/style.css` | Glass panels, camera layers, and responsive layout |
| `frontend/src/hooks/useCamera.js` | Camera permission, selection, stream lifecycle, and errors |
| `frontend/src/lib/cameras.js` | Session camera IDs such as 0x001, preserving browser device IDs for selection |
| `frontend/src/components/CameraSettings.jsx` | Detected-camera list, active indicator, and camera selection |
| `frontend/tests/cameras.test.js` | Camera ID continuity, reconnect, and permission-hidden device tests |
| `frontend/src/components/HandOverlay.jsx` | Worker lifecycle and aligned landmark drawing |
| `frontend/src/workers/hands.js` | Local MediaPipe hand inference |
| `frontend/src/components/ModelViewer.jsx` | Optional Three.js GLB viewer |
| `frontend/public/models/README.md` | Model placement instructions |
| `backend/main.py` | Health, sensor status, and ESP32 wire-input REST endpoints |
| `backend/requirements.txt` | Python dependencies |
| `AR model/README.md` | Blender source/model folder instructions |

Reference: [MediaDevices device changes](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/devicechange_event) and [MediaPipe JavaScript hand tracking](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/web_js).
