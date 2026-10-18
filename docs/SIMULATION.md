# Student simulation, assessment, and monitor

## Run a student session

1. Start the app using [the Windows run guide](RUNNING.md).
2. One of the 10 fictional patients is assigned at startup. There is no patient dropdown or Random Patient button.
3. Press **Start Simulation** in the workspace bar. The assigned patient's information stays fixed throughout this student's simulation.
4. In **Patient Info**, review the details and press **Confirm patient reviewed**. This records your acknowledgement in the checklist.
5. Open **Vitals**. With the wire requirement off, the simulated monitor initializes automatically during the session. If the requirement is on, connect the selected simulated/hardware wire source first. Wire controls are under **Wire activation settings** in Vitals or in Settings.
6. Open **Assessment → Checklist** to see completed actions and what remains. Record a drug choice, identify a scripted monitor change, and record your intervention.
7. Open **Assessment → Feedback** to see a timestamped record of what you did and the unfinished tasks.
8. Press **End Simulation** when the student is finished. This closes the session even if tasks are incomplete, keeps that student's report, clears the next student's checklist and drafts, and randomly assigns a different patient. The simulated wire switch also resets to disconnected. The physical ESP32 signal continues to reflect its actual state.
9. The next student's patient is now visible and fixed. Press **Start Simulation** when that student is ready. The previous report remains available in Feedback until the next simulation ends, when it is replaced by that session's report.

The patient never changes due to a scenario change, slider adjustment, wire disconnect, or panel change. Student numbers increase after ending sessions. Data is currently kept in memory only: reloading the page resets the session, randomly assigns an initial patient again, and discards reports. Export/persistent student records are not implemented yet.

## Checklist and feedback

The checklist tracks these app actions:

- Acknowledged reviewing the assigned patient.
- Initialized the simulated monitor during a running session.
- Recorded a drug selection.
- Matched an observation to a scripted monitor condition.
- Recorded an intervention description.

Feedback shows the action times, the selected drug and written intervention, recognition attempts, and which tasks were not recorded. A wrong recognition attempt stays in the action log and does not complete the recognition task. To test recognition, select **Reduced respiration**, **Exaggerated activity**, or **Recovery** in the monitor controls, then record the matching observation in Assessment. Baseline has no scripted change to identify. Manual slider changes are visual demonstrations; recognition matching uses the selected scripted condition.

Completion counts describe the workflow only. Drug appropriateness, physical technique, and intervention quality need instructor review and are not automatically graded. The system does not infer a procedure from hand landmarks. Written actions and patient-review acknowledgements are student-reported.

## Animated simulated vitals

The monitor starts only after **Start Simulation**, provided the optional wire gate allows it. Otherwise it shows dashes and empty grid backgrounds rather than a stale patient trace. When the wire signal is lost, monitored simulation time and waveforms pause and beeps stop. Reconnection resumes that session; it does not change the patient.

Values vary over time with small baseline differences between fictional patients. By default, the demo cycles through **Baseline → Reduced respiration → Exaggerated activity → Recovery**, spending 30 monitored seconds in each condition. The demo repeats until the session ends. Timers pause while the browser tab is hidden; this is not a background clinical monitor.

Under **Simulation controls**, choose a condition immediately or adjust any parameter slider. Selecting a condition or slider disables automatic cycling. Enable auto-cycle again to return to the time-based sequence; its phase follows total monitored time. Conditions and sliders change visual signals directly; they are not drug-effect or validated disease models.

| Channel | Visual behavior |
| --- | --- |
| HR / ECG | Distinct ECG-like peaks; higher simulated HR increases repetition and illustrative amplitude. Zero HR stops the heartbeat sound. |
| Respiratory rate | A breathing wave that becomes smaller/slower at low RR and larger/faster at high RR. Zero RR stops the respiratory cycle. |
| SpO₂ / Pleth | A pulse-shaped trace whose amplitude follows the simulated saturation; repetition follows HR. |
| Blood pressure / MAP | A pressure-like pulse whose height follows MAP and repetition follows HR. The displayed number is MAP, not a systolic/diastolic pair. |
| EtCO₂ / Capnogram | A plateau-shaped trace whose height follows CO₂ and repetition follows RR. |
| Temperature | A slow illustrative trend, not an ECG-style heartbeat trace. |

These waveform height mappings are visual effects requested for demonstration. They are not clinically validated relationships, diagnostic measurements, or actual sensor data. Choosing a drug does not automatically modify the simulated values.

## Heartbeat beep

Click **Enable beep** in Vitals, or **Enable heartbeat beep** in Settings. It is off by default. A short synthesized tone repeats at the current simulated HR while the monitor is running; higher HR produces faster beeps. It continues when you change panels. Mute it using the same control. Ending the session, losing the wire signal, or hiding the browser tab stops beeps. If left enabled, it resumes when the next session's monitor starts.

No audio file or audio API service is required. The browser generates sound locally using Web Audio. Sound is enabled through a user click to comply with [browser audio playback rules](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices). If sound is unavailable or blocked, the monitor remains usable and shows an error message.

## Verify the change

From `frontend`, run:

```powershell
npm.cmd test
npm.cmd run build
```

The automated tests cover fixed patient assignment, patient rotation on completion, separate student reports/checklists, wire gating, recognition feedback, auto-cycling, and waveform rate/amplitude calculations. They do not verify your browser's audio output, rendered camera alignment, or physical hardware.

For a manual check: start a session, set reduced respiration, observe smaller/slower breathing waves, enable sound, raise HR, and listen for faster beeps. Try RR and HR at zero using the sliders. Disconnect the test wire and confirm traces/beeps stop. End the session and verify that the next patient differs and the previous report still names the previous patient.
