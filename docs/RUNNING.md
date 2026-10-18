# How to run the project (Windows 10 / 11)

This guide is for groupmates downloading the project from GitHub. Run it locally on your own computer. You do not need an ESP32, sensors, or the Blender model to try the interface.

## 1. Install these first

| Software | Needed for |
| --- | --- |
| Node.js 22 or newer, with npm | Required: React frontend |
| A recent Chrome or Microsoft Edge browser | Required: camera and hand tracking |
| Git | Optional: cloning and pulling updates; Download ZIP also works |
| Python 3.10 or newer | Optional: FastAPI backend and ESP32 wire input |

After installing software, close and reopen your terminal. Check your installation in PowerShell:

```powershell
node --version
npm.cmd --version
```

These print the Node.js and npm versions. If running the backend, also check:

```powershell
py --version
```

If `py` is unavailable but `python --version` works, use `python` instead of `py` when creating the virtual environment below.

Internet is required to install packages. Hand tracking also currently downloads its pretrained model and runtime files from Google and jsDelivr when enabled. Detection itself runs locally in your browser; it does not use a remote inference API or send camera frames to Python.

## 2. Get the project

### Option A: Git clone

The project repository is [gabrieltaala-eng/PD1](https://github.com/gabrieltaala-eng/PD1). In PowerShell, open the directory where you want to keep the project, then run:

```powershell
git clone https://github.com/gabrieltaala-eng/PD1.git Veterinary-Anesthesia-AR
cd Veterinary-Anesthesia-AR
```

`git clone` downloads PD1 into a local folder named `Veterinary-Anesthesia-AR`; `cd` opens that folder. The local folder name is set explicitly so the commands in this guide stay consistent.

### Option B: Download ZIP

Click **Code → Download ZIP** on GitHub. Extract the ZIP completely. Open the extracted folder in VS Code, then choose **Terminal → New Terminal**. Make sure you are in the project root: the folder containing this structure:

```text
Veterinary-Anesthesia-AR/
├── frontend/
├── backend/
├── AR model/
├── docs/
└── README.md
```

All commands below assume you start in that project root, wherever it is saved on your computer. Do not copy another groupmate's absolute file path.

## 3. Start the frontend (required)

In your first PowerShell terminal, starting at the project root:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

- `cd frontend` opens the React application folder.
- `npm.cmd ci` installs the exact package versions in `package-lock.json`. Run this on first setup and after dependency updates. It replaces an existing `node_modules` folder.
- `npm.cmd run dev` starts the Vite development server. Leave this terminal running.

Open the **Local** URL printed by Vite, normally **http://127.0.0.1:5173**. If that port is busy, Vite may choose another port; use the URL actually printed.

The interface should now work. **Backend offline** is expected if you have not started Python. It does not prevent the camera, hand tracking, patient selector, or simulated wire controls from working.

For later launches, you normally only need to run `npm.cmd run dev` from `frontend`.

## 4. Try the interface without hardware

1. Click **Start Camera** and allow the browser to access your camera.
2. For a USB webcam, open **Settings → Camera selection**, choose it under **Camera device**, and click **Apply / Restart**. Detected cameras show app IDs such as **0x001 — Integrated Webcam** or **0x002 — USB Camera**, with the active device marked. IDs are assigned to both built-in and peripheral cameras; the browser supplies the names. The numbering depends on discovery order, not on camera type.
3. Press **Start Simulation**. Open **Patient Info**, review the assigned patient, and press **Confirm patient reviewed**. There is no patient picker; the patient stays fixed during this simulation.
4. Open **Vitals**. Values change with scripted demo conditions. Click **Enable beep** for a heartbeat sound. Open **Simulation controls** to test lower/higher RR and other values; the waveforms respond to the simulated parameters.
5. In **Wire activation settings** (or Settings), enable **Require wire connection for vitals**. Keep **Simulated wire (no ESP32 needed)** selected.
6. Turn **Simulate wire connected** on: sample vitals appear. Turn it off: the readings pause and show dashes. Disable the wire requirement to display vitals normally again.
7. Open **Tracking** and enable **Hand skeleton overlay**. Keep internet available for the model download, then show one or two hands to the webcam.
8. Switch panels and confirm the camera continues running. Try the overlay, mirror, and full-screen controls.
9. Open **Assessment → Checklist** for unfinished tasks. Record a drug choice, identify a scripted change, and write/record an intervention. Open **Feedback** for the action log and missing tasks.
10. Press **End Simulation**. A different patient is randomly assigned for the next student, whose checklist starts empty. The previous student's feedback report stays available until the next simulation ends.

Assessment tracks recorded workflow actions; it does not clinically grade drug choices or interventions. Patient assignment, wire toggles, and reports are in memory only and reset on page reload. See [simulation instructions](SIMULATION.md) for the full flow and waveform behavior.

Camera IDs such as `0x001` are friendly labels assigned by this app, not USB vendor/product IDs. They remain stable for identified devices during the mounted app session, including list reordering and reconnecting the same browser device ID. Refreshing the page starts a new numbering session; browser permission/privacy changes can also change device identifiers. Camera names and the complete selectable list may require camera permission first; see [browser device enumeration](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/enumerateDevices).

To test selection, connect two cameras, allow access, and press **Refresh camera list**. Select each camera and apply it, confirming the displayed view and Active camera indicator change. Disconnect the selected camera; a message should appear and the app should not silently choose another. Reconnect it and refresh the list; its app ID should be retained for the current session if the browser reports the same device ID.

## 5. Start the backend (optional)

Use this when checking API status or preparing ESP32 communication. Open a **second terminal at the project root**, leaving the frontend running in the first terminal.

First setup:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- `cd backend` opens the Python service folder.
- `py -m venv .venv` creates a project-specific Python environment. Create your own; do not copy someone else's `.venv`.
- The pip command installs the backend dependencies into that environment.
- The uvicorn command starts FastAPI on port 8000. `--reload` automatically restarts it after Python edits. Leave this terminal running too.

This uses the virtual environment's Python directly, so you do **not** need to activate it or change PowerShell execution policies.

Open **http://127.0.0.1:8000/docs** to view the API. The frontend should show **Backend online** shortly afterward. Vite forwards `/api` requests to port 8000.

For later launches, from `backend` run only:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

No physical hardware is required to run the backend. Missing angle/volume readings remain unavailable. The **ESP32 hardware** wire source waits for actual messages; plugging in a USB cable alone does not report wire state. Board firmware and GPIO configuration are still needed. See [patient and wire instructions](patients-and-wire.md) for the expected heartbeat messages.

## 6. Optional Blender model

Save the exported model as:

```text
frontend/public/models/canine.glb
```

Open **3D Patient**. Drag to rotate and scroll to zoom. If the model includes animation clips, the first clip plays automatically. Without the file, a placeholder is normal and the rest of the application works.

See [the model folder instructions](../AR%20model/README.md). The 3D viewer is not yet anchored to the physical dummy.

## 7. Run checks

In a separate terminal, from `frontend`:

```powershell
npm.cmd test
npm.cmd run build
```

`test` checks patient selection and vitals activation rules. `build` compiles the frontend into `frontend/dist/`. It does not verify your physical webcam or ESP32.

To serve that built frontend locally, from `frontend` run:

```powershell
npm.cmd run preview
```

Open the printed URL. This serves the production build for local testing; it is separate from the development server.

From `backend`, after installing its dependencies:

```powershell
.\.venv\Scripts\python.exe -m unittest test_wire.py test_wire_api.py
```

This checks wire heartbeat expiry and API input validation. No ESP32 is needed for these automated tests.

## 8. Stop and update the project

Press **Ctrl+C** in each running server terminal to stop it. You can also click **Stop Camera** to release the webcam without stopping the app.

If you cloned with Git, stop the servers and run the following from the project root to download group updates:

```powershell
git pull
```

Save and commit your own work before pulling. If Git reports conflicts, resolve them with your group instead of discarding local edits. If `frontend/package.json` or `frontend/package-lock.json` changed, run `npm.cmd ci` in `frontend` again. If `backend/requirements.txt` changed, rerun the backend pip-install command. Then restart the servers.

If using Download ZIP, download/extract a new copy separately and preserve any local changes you made.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `node`, `npm`, or `git` not recognized | Install the missing tool, then reopen the terminal. Git is unnecessary for the ZIP option. |
| PowerShell blocks `npm.ps1` | Use `npm.cmd`, as shown above. |
| Cannot find `package.json` | Run frontend commands from `frontend`, not the project root or `backend`. |
| `npm.cmd ci` reports a missing lockfile | Ensure `frontend/package-lock.json` was included in the repository. |
| Browser cannot open the app | Keep `npm.cmd run dev` running and use its printed Local URL. |
| Camera permission denied | Allow camera access in browser site settings and Windows camera privacy settings, then retry. |
| Camera unavailable | Reconnect the webcam, refresh the device list, select it, and close other programs using it. |
| Camera fails on a LAN URL or GitHub page | Run the project on your computer using localhost. Camera access needs localhost or HTTPS; opening the source files or repository page does not start the app. |
| Hand tracker cannot load | Check internet access to Google Storage and jsDelivr; try disabling tracking and enabling it again. Hand tracking does not need FastAPI. |
| Backend offline | This is normal for frontend-only testing. Otherwise check the second terminal and confirm FastAPI is running on port 8000. |
| Backend port 8000 is occupied | Stop the other process if it belongs to you. The frontend proxy expects port 8000; changing the backend port requires updating `frontend/vite.config.js` too. |
| `No module named fastapi` or `uvicorn` | Install requirements using `.venv\Scripts\python.exe`, and use that same interpreter to start the backend. |
| `py` opens the Store or is unavailable | Install Python, reopen the terminal, or use a working `python` command to create `.venv`. |
| 3D model is missing | The placeholder is expected until `canine.glb` is added at the exact path above. |
| Vitals show dashes | Press Start Simulation first. Then check whether the wire requirement is on and whether its selected source is connected. For testing without hardware, choose Simulated wire. |

## Before uploading to GitHub

Include the source folders, documentation, `frontend/package.json`, `frontend/package-lock.json`, `backend/requirements.txt`, and `.gitignore`.

The supplied `.gitignore` excludes `frontend/node_modules/`, `frontend/dist/`, `backend/.venv/`, Python caches, and local `.env` files. Each groupmate installs their own dependencies. Do not upload passwords, Wi-Fi credentials, or local virtual environments.

GitHub stores the project source; groupmates still run the commands above on their own computers. Publishing a GitHub repository does not start Vite or FastAPI, and GitHub Pages does not run the Python backend.
