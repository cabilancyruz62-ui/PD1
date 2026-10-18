# How to run the project (Windows 10 / 11)

This guide is for groupmates downloading [gabrieltaala-eng/PD1](https://github.com/gabrieltaala-eng/PD1). The assessment runs locally on your computer. **Start both frontend and backend.** Hardware simulation is included, so an ESP32, syringe sensors, RFID reader, and dog model are not required for first testing.

## 1. Install prerequisites

| Software | Purpose |
| --- | --- |
| Node.js 22 or newer, including npm | React frontend |
| Python 3.10 or newer | FastAPI assessment backend |
| A recent Chrome or Edge browser | Web interface, camera, hand tracking and sound |
| Git (optional) | Clone and update the repository; Download ZIP also works |

Close/reopen your terminal after installing software. In PowerShell:

```powershell
node --version
npm.cmd --version
py --version
```

These print installed versions. If `py` is unavailable but `python --version` works, replace `py` with `python` when creating the environment below. Internet is needed for dependency installation and the current hand-tracker model/runtime downloads. Inference itself runs locally, without sending camera frames to an API.

## 2. Download the repository

Open PowerShell in the directory where you want the project, then run:

```powershell
git clone https://github.com/gabrieltaala-eng/PD1.git Veterinary-Anesthesia-AR
cd Veterinary-Anesthesia-AR
```

`git clone` downloads the repository into the explicitly named folder. `cd` opens it. Alternatively choose **Code → Download ZIP** on GitHub, extract it fully, open the extracted folder in VS Code, and open a terminal there.

Your project root must contain `frontend`, `backend`, `AR model`, `docs`, and `README.md`. All commands below start at that root in a new terminal. Do not copy another person's Desktop path.

## 3. Start FastAPI — terminal 1

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- `cd backend` selects the Python folder.
- `py -m venv .venv` creates your own isolated environment. Do not copy a groupmate's `.venv`.
- The pip command installs the backend and WebSocket dependencies.
- Uvicorn starts FastAPI on port 8000 and reloads Python edits. Leave the terminal open. Using the environment's Python directly avoids PowerShell activation restrictions.

Open **http://127.0.0.1:8000/docs** to confirm the API is running. Later launches only need the final uvicorn command from `backend`.

If updating from an older version, rerun the pip command: the two-mode workflow adds a WebSocket dependency. Restarting the backend preserves saved records, but interrupts unfinished sessions.

## 4. Start React — terminal 2

Open a second terminal at the project root:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

- `cd frontend` selects the folder containing `package.json`.
- `npm.cmd ci` installs the exact `package-lock.json` versions and replaces an existing `node_modules`. Use it for first setup and after dependency changes.
- `npm.cmd run dev` starts Vite; leave it running. Later launches normally need only this command from `frontend`.

Open the printed **Local** URL, usually **http://127.0.0.1:5173**. If a port is occupied, use the actual URL printed by Vite. Do not open `index.html` directly or use the GitHub repository page as the running application.

The two assessment cards should be selectable. If they are disabled, start/check FastAPI on port 8000. Camera and hand tracking can run without FastAPI, but assessment, RFID matching, timing, and scoring require it.

## 5. Test both modes without hardware

Read **[the full two-mode guide](TWO_MODES.md)** for step-by-step tests, message examples, exact file paths, and scoring rules.

For a quick check:

1. Choose Option 1, review the patient, and select a complication in Scenario.
2. Begin Injection, then choose Hardware → Valid angle · 22°.
3. Press Complete Injection within five seconds of that sample. The complication starts.
4. Record the complication in Assessment → Checklist.
5. In Hardware, try Incorrect RFID tag, then Correct RFID tag. **Drug Verified** unlocks intervention injection and automatically opens the angle panel. Record a **new** valid/invalid angle, then press **Complete Intervention Injection**. RFID selection alone does not finish the assessment.
6. Review both angle results and timing in Feedback. End Assessment, choose Option 2 for the next patient, then Start Scenario. Option 2 skips the initial anesthesia injection, but after Drug Verified it still requires the shared intervention angle check and completion confirmation in the simulated injectable exercise.

Only one complication is active. There is no automatic complication cycle. Drug 1–3, angle rules, and scoring are demonstration placeholders awaiting licensed veterinary review.

See [the updated angle/injection guide](ANGLES_AND_INTERVENTION.md) for stage IDs, smoothing, quaternion calibration, and route approval. Configured non-injectable interventions do not require an injection; real unapproved injectable routes wait for veterinary review.

## 6. Camera, hands, sound, and dog model

Open **Settings → Camera selection**, press Start Camera and allow permission. Choose your webcam and Apply / Restart. Examples such as **0x001 — Integrated Webcam** and **0x002 — USB Camera** are session labels assigned by the app, not USB hardware IDs. Camera names may only appear after browser permission. The same identified camera keeps its label during a mounted app session, including reordering/reconnection; page reload starts a new numbering session.

Camera access needs localhost or HTTPS. The app requests no microphone access. Switching panels or displaying RFID feedback keeps the video mounted. Use Refresh camera list after connecting another webcam. A disconnected selection does not silently switch to a different camera.

Enable **Hand skeleton overlay** in Tracking or Settings, with internet available for the model download. It tracks hands only; syringe angle comes from calibrated hardware or explicit simulation controls.

Click **Enable beep** in Vitals or **Enable heartbeat beep** in Settings. Sound is off by default and follows simulated HR while the monitor is active. Browser audio needs a user click. Hiding the tab or pausing monitor display stops beeps.

For the dog viewer, place the Blender export at `frontend/public/models/canine.glb` and open 3D Patient. Without it the placeholder is expected. Drag to rotate and scroll to zoom. Physical-dummy anchoring is not yet implemented.

## 7. Optional wire gate

Vitals → Optional wire activation settings, or Settings, can require a separate wire signal to show the monitor. Keep this off for initial assessment tests. For a hardware-free demonstration, choose Simulated wire and toggle Simulate wire connected. It controls monitor visibility/audio only; it is not injection completion, drug selection, or a heart-rate measurement. It does not reset the backend response timer. See [wire instructions](patients-and-wire.md).

## 8. Checks, stopping, and updates

From `frontend`:

```powershell
npm.cmd test
npm.cmd run build
```

The first command runs frontend logic checks. The second compiles the production assets into `frontend/dist`. `npm.cmd run preview` serves that build locally at a printed URL, with FastAPI still required for assessment.

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"
```

This tests wire handling, assessment rules, SQLite records, HTTP validation, and live WebSocket communication using temporary records. It does not verify physical sensors or browser visuals.

Press **Ctrl+C** in each server terminal to stop it. Stop Camera releases the webcam independently. After ending a student's session, saved records remain in `backend/data/assessments.sqlite3`; this directory is excluded from Git.

For Git updates, save/commit your own work, stop the servers, and run `git pull` from the project root. Resolve conflicts with your group. Run `npm.cmd ci` again if frontend dependencies changed, and rerun the backend pip command if requirements changed. Restart both servers. ZIP users should extract a new copy separately while preserving local edits and assessment data.

## Troubleshooting

| Problem | Action |
| --- | --- |
| `npm` / Node / Python not found | Install the relevant tool, then reopen the terminal. |
| PowerShell blocks `npm.ps1` | Use `npm.cmd`, as shown above. |
| `ENOENT package.json` | You are probably at the project root. Run `cd frontend` before npm commands. |
| `No module named fastapi` / `uvicorn` | Install requirements with `.venv\Scripts\python.exe` and use that same interpreter to start FastAPI. |
| Unsupported WebSocket upgrade | Rerun the backend pip-install command to install `websockets`, then restart FastAPI. |
| Assessment cards disabled / backend offline | Check the FastAPI terminal, port 8000, and frontend `/api` proxy. The assessment needs both servers. |
| Port 8000 occupied | Stop the other process only if it belongs to you. Changing this port also requires updating the Vite proxy target. |
| Camera unavailable / denied | Allow browser/Windows camera access, close other webcam apps, reconnect the selected device, and refresh the list. |
| Hand tracker cannot load | Check connectivity to Google Storage and jsDelivr; disable/re-enable tracking. FastAPI is not used for hand inference. |
| Complete Injection rejected | Begin the initial injection (Option 1) or verify the RFID drug to unlock intervention injection (both options). Supply a new fresh calibrated sample for that stage. Samples expire after five seconds and cannot be reused across stages. |
| Correct tag test ignored | Start the scenario, ensure it is active, and reconnect simulated sensors if disconnected. Allow 1.5 seconds for same-tag debounce. |
| Real ESP32 scan rejected | Check current `session_id`, status heartbeat, input source, UID registry, and event schema in the two-mode guide. |
| Vitals show dashes | Choose a mode, verify backend connection, then check the optional wire gate. |
| Missing model | Add `canine.glb` at the exact path; the placeholder is otherwise normal. |

Keep source, docs, dependency lockfiles, and `.gitignore` in Git. Do not commit `node_modules`, `.venv`, local records, `.env` secrets, or Wi-Fi credentials. Each groupmate installs their own environment. GitHub stores the source; it does not launch Vite or FastAPI, and GitHub Pages cannot run this Python backend.
