# Simulation and assessment

The browser-only, automatically cycling demo has been replaced by **two backend-managed assessment modes**. Please use the current **[two-mode simulation guide](TWO_MODES.md)**.

- Option 1 includes a fresh calibrated angle check and explicit injection confirmation before a complication.
- Option 2 goes directly from baseline to a complication, then requires intervention angle assessment and explicit injection completion after RFID verification. Only the initial anesthesia injection is skipped.
- One of three complications stays selected until evaluation or End Assessment.
- Registered RFID UIDs select placeholder Drug 1–3. Wrong/unknown attempts remain recorded; duplicates are filtered.
- Correct RFID displays Drug Verified; it does not finish the assessment. Both modes share the calibrated/smoothed intervention angle module. See [the updated angle and injection guide](ANGLES_AND_INTERVENTION.md) for route approval and separate initial/intervention records.
- Checklist shows outstanding tasks; Feedback shows actions, first/subsequent response times, and the configurable placeholder score.
- End Assessment saves the report locally and assigns a different patient for the next student.
- Refreshing the browser reconnects to backend state. Restarting the backend interrupts unfinished sessions and retains records in SQLite.

Both frontend and backend are required for the assessment, with no physical hardware required in simulation mode. See [Windows setup](RUNNING.md) and [optional wire gate](patients-and-wire.md). Camera, monitor beeps, and the optional GLB viewer remain supported. No clinical validation or Electron packaging is claimed.
