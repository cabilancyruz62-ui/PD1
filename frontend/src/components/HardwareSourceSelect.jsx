import { useId } from 'react';

export default function HardwareSourceSelect({ state, onChange, disabled, disabledReason }) {
  const helpId = useId();
  if (!state) return <p className="notice">Waiting for the backend.</p>;
  const locked = !['mode_selection', 'preparation'].includes(state.phase);
  const message = locked ? 'The input source stays fixed during an exercise. End the assessment to change it for the next one.'
    : disabled ? disabledReason || 'Wait for the current action to finish and check the backend and camera connections.'
      : !state.mode ? 'Choose your input source now, or change it during assessment setup.'
        : 'You can change the input source until Begin Injection or Start Scenario.';
  return <div className="hardware-source-select">
    <label className="field">Hardware input source<select value={state.input_source} disabled={disabled || locked} aria-describedby={helpId} onChange={event => onChange(event.target.value)}><option value="simulation">SIMULATED · no ESP32 required</option><option value="esp32">REAL · ESP32 hardware</option></select></label>
    <p id={helpId} className="notice" role="status">{message}</p>
  </div>;
}
