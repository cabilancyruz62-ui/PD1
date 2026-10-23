# Both modes: intervention injection and angle assessment

This update supersedes the original RFID-only completion flow. Start both servers using [RUNNING.md](RUNNING.md). No Electron code or firmware flashing is included.

## Student flow

| Step | Option 1 | Option 2 |
| --- | --- | --- |
| Initial anesthesia injection | Required, with its own angle and confirmation | Skipped |
| One complication | Required | Required |
| Registered RFID drug verification | Required | Required |
| Intervention injection exercise | Required for simulated injectable routes | Required for simulated injectable routes |
| Intervention angle | New reading, separate from the initial angle | Same shared module and target |
| Completion | Explicit confirmation, never inferred from angle/RFID | Same explicit confirmation |

Incorrect and unknown tags stay at the complication/RFID stage. Correct RFID displays **Drug Verified**, records the selection/time, and unlocks `intervention_injection`. The score remains provisional. The Scenario panel opens automatically with student angle feedback, without restarting the webcam. Open the **Hardware** navigation tab for sensor setup and testing controls. The angle card stays inside Scenario and Hardware; on wider screens Vitals remains beside the active panel.

An acceptable angle alone does not complete either injection. A fresh out-of-range angle can still be manually confirmed: it is recorded as a failed angle criterion, rather than forcing every student to achieve a passing result before ending the exercise.

## During-assessment feedback

During Feedback appears in a popup while an assessment is running. A wrong registered RFID drug displays a warning icon and a concise message such as **Wrong drug: Drug 2 for Hypotension.** An unknown RFID tag is identified separately, without inferring a drug name. Continue or Escape dismisses the popup. Completed reports retain all recorded attempts under **Assessment > Post Feedback**.

During either injection stage, the feedback popup and live angle card display **Angle too low**, **Angle too high**, or **Angle within accepted range** using the configured inclusive range. A stale, uncalibrated, missing, or prior-stage reading shows a waiting message. The popup waits for an actual sample and does not reopen for each new reading with the same result. When raw and smoothed readings differ, feedback identifies which one is outside the target; the backend still requires both readings to pass.

To try it with simulated inputs, start a scenario, identify it in **Assessment > Checklist**, open **Hardware**, and submit **Incorrect RFID tag**. Inspect and dismiss the popup. Then scan **Correct RFID tag**, continue to the intervention, and try the **Low angle**, **High angle**, and **Valid angle** buttons in Hardware. With the default 15°–30° range, these generate 10°, 45°, and 22.5° respectively. Refresh each sample before the five-second freshness window expires. Both injection stages use the same feedback rules; injection completion remains a separate manual action.

## Test Option 1 without hardware

1. Select Option 1 and a complication during preparation. Keep Hardware input source **SIMULATED**.
2. Begin Initial Injection. Click **Valid angle · 22.5°**, **Low angle · 10°**, or **High angle · 45°** in Hardware, then dismiss the feedback popup.
3. Within five seconds, press **Complete Initial Injection**. The initial angle/result is frozen and the complication starts.
4. Record recognition in Assessment. Try an incorrect RFID first if desired; it must not unlock injection.
5. Submit Correct RFID tag. The Drug Verified popup appears; continue to the automatically opened Scenario panel. Open Hardware for simulated test inputs.
6. Confirm the live angle initially shows no sample for this new stage. The initial angle cannot be reused.
7. Generate a new angle and press **Complete Intervention Injection**. Only now are final results available.
8. In Feedback, check initial angle, intervention angle, both completion statuses, first RFID response, intervention duration, total time to intervention completion, and score.

Each synthetic angle button generates five explicitly simulated identical samples so the filter can settle for a usable demonstration. It does not claim that a physical device supplied five measurements.

## Test Option 2 without hardware

1. Select Option 2, review baseline vitals, choose a complication, and Start Scenario.
2. Record recognition and scan an incorrect/unknown RFID. The scenario stays active; injection remains locked.
3. Submit Correct RFID. Drug Verified unlocks the intervention angle stage.
4. Generate a **new** angle and explicitly confirm Complete Intervention Injection.
5. Feedback must show initial anesthesia as skipped, an intervention angle/result, and the final placeholder score. Initial criteria do not appear in this mode's scoring.

For both modes, also test stale samples (wait five seconds), sensor disconnection, duplicate RFID reads, and ending before completion. None should automatically complete an injection. Camera panels can be opened/collapsed while the same video stream continues.

## Separate records and timing

The state and saved SQLite report include:

- `initial_angle` (Option 1 only; `injection_angle` is retained as a legacy alias).
- `intervention_angle` and `intervention_injection_completed`.
- Distinct `injection_stage_id` values for each injection.
- `angle_records.initial` and `angle_records.intervention`: total sample counts, within-target counts, and the latest 200 sample records for each stage.
- Raw and smoothed angles, calibration ID, source, calculation method, freshness, target result, and any applied quaternion calibration.
- All scored RFID attempts and incorrect/unknown selections.
- `first_response_seconds`: scenario-visible acknowledgement to first submitted RFID intervention; unchanged by retrying or injecting.
- `intervention_duration_seconds`: correct verification to explicit completion.
- `intervention_completion_seconds`: scenario onset to explicit completion.

The final confirmation freezes that stage's angle/result. Changing or disconnecting sensors afterward does not rewrite completed angle records. The next student gets clean stage records; the previous student's result remains saved. Historical reports from the old version are displayed as legacy assessments without inventing missing intervention angles.

## Shared calibrated angle module

`backend/angles.py` is used by both injection stages in both modes. It supports:

1. **Firmware-computed surface angle:** supply finite `angle_deg` in 0–90°, `calibrated:true`, and a nonempty `calibration_id`. This is an explicit device assertion that the result is relative to the calibrated skin plane; it is not proof that the calibration is accurate.
2. **Paired orientations:** supply both sensor quaternions and a calibration registered in `angle_calibrations`. The backend rotates the syringe axis and dummy surface normal into their calibrated common reference frame and calculates `degrees(asin(abs(dot(unit_axis, unit_normal))))`. This is the angle to the plane, not its normal, and does not subtract Euler pitch.

Quaternions use active rotations in scalar-last `[x, y, z, w]` order. Sensor mounting vectors and sensor-reference alignment must be measured, not assumed. A configuration *shape* is shown below; these identity rotations and example axes are not a calibration for your physical dummy:

```json
"angle_calibrations": {
  "EXAMPLE_ONLY_REPLACE_WITH_MEASURED_CALIBRATION": {
    "syringe_axis_sensor": [1, 0, 0],
    "surface_normal_sensor": [0, 0, 1],
    "syringe_reference_rotation_xyzw": [0, 0, 0, 1],
    "dummy_reference_rotation_xyzw": [0, 0, 0, 1]
  }
}
```

Default calibration registration is empty. Unknown/zero/missing quaternion calibration is unassessable, even if an extra numeric angle was included in the packet; the backend does not silently fall back to an unverified value. Sensor fusion, relative frame alignment, yaw drift, and mounting accuracy still require physical validation. Smoothing reduces jitter; it does not correct bad calibration or drift.

The exponential filter uses configurable `angle_smoothing_alpha` (default 0.35). It resets on a new stage, source/calibration/method change, stale gap, or disconnection. Completion requires a fresh calibrated sample from the current stage. For the target criterion to pass, **both the latest raw and smoothed angles must be within the inclusive 15°–30° target**; smoothing cannot conceal a latest out-of-range sample.

Math references: [scalar-last quaternion conventions](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.from_quat.html) and [line/plane angles](https://docs.sympy.org/latest/modules/geometry/plane.html). The implementation uses Python's standard library; SciPy and SymPy are not runtime dependencies.

## ESP32 packet changes

Before sending angle samples, read both `session_id` and `injection_stage_id` from `/api/assessment/state` (or the hardware WebSocket acknowledgement). The stage ID changes after initial completion and after Drug Verified. Send the current one on every angle event:

```json
{"type":"angle","source":"esp32","device_id":"esp32-station-1","event_id":"boot-A-angle-27","session_id":"CURRENT_SESSION","injection_stage_id":"CURRENT_INJECTION_STAGE","angle_deg":22.0,"calibrated":true,"calibration_id":"YOUR_MEASURED_CALIBRATION"}
```

For backend quaternion calculation, replace `angle_deg` with both `syringe_quaternion` and `dummy_quaternion` and use a registered calibration ID. Send sensor-to-reference quaternions in the documented order, synchronized in one packet.

The browser also supplies the current stage ID on Complete Injection. Old stage IDs are rejected. Replayed angle event IDs do not feed the smoother again or refresh freshness. Use unique event IDs for genuine new samples and reuse IDs on transport retries. Continue the one-second ESP32 status heartbeat; both samples and sensor connection must be fresh.

## Injectable-route rule

Each scenario now configures `intervention_route` (`injection` or `non_injectable`) and `injectable_expert_approved` in `backend/config/assessment.json`.

| Configuration/source | Behavior after Drug Verified |
| --- | --- |
| Simulation + injection route | Clearly labeled injection/angle demonstration; not clinically approved |
| ESP32 + injection route + expert approval | Intervention angle and explicit injection completion required |
| ESP32 + injection route without approval | Waits at `intervention_review`; no injection is required/unlocked |
| Non-injectable route | No syringe-angle criterion; separately confirm the non-injectable intervention |

All shipped Drug 1–3 routes remain unapproved placeholders. Do not change an approval flag simply to bypass a blocked hardware demonstration: first obtain the licensed expert's route decision. For example, hypoventilation may need airway/ventilation management rather than injection. None of these mappings recommends an actual medication. Route configuration is loaded on backend startup; changing it interrupts an unfinished assessment, so finish the session first.

## Updated placeholder weights

| Mode | Initial angle | Initial completion | Recognition | RFID drug | Intervention angle | Intervention completion |
| --- | --- | --- | --- | --- | --- | --- |
| Option 1 | 15 | 15 | 15 | 25 | 20 | 10 |
| Option 2 | — | — | 20 | 35 | 30 | 15 |

Scores remain configurable and unvalidated. Incorrect/unknown active-scenario RFID attempts still subtract 5 points each by default. For non-injectable or review-blocked routes, the intervention-angle weight is excluded from the denominator. Generic intervention completion remains a criterion; no automatic full score is awarded just for RFID verification. End Assessment can save an incomplete result.

## Files and checks

New code: `backend/angles.py`, `backend/test_angles.py`, `backend/test_injection_workflow.py`, and `frontend/src/components/InjectionAngle.jsx`. Updated code: `backend/assessment.py`, `backend/assessment_models.py`, `backend/config/assessment.json`, `backend/main.py`, `backend/test_assessment.py`, `backend/test_transports.py`, `frontend/src/hooks/useAssessment.js`, `frontend/src/lib/assessmentView.js`, `frontend/src/App.jsx`, `frontend/src/components/ModeSelection.jsx`, `frontend/src/components/SimulationControls.jsx`, `frontend/src/components/ScenarioPanel.jsx`, `frontend/src/components/HardwarePanel.jsx`, `frontend/src/components/InterventionNotice.jsx`, `frontend/src/components/AssessmentPanel.jsx`, `frontend/src/style.css`, and `frontend/tests/assessment.test.js`.

From `frontend`, run `npm.cmd test` and `npm.cmd run build`. From `backend`, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py"
```

Tests cover both injection stages, separate records, stage/packet replay protection, stale samples, raw-vs-smoothed target checks, quaternion geometry, unapproved/non-injectable routes, and real HTTP/WebSocket exchanges using temporary records. Physical sensor calibration, camera rendering, and audio remain manual checks.
