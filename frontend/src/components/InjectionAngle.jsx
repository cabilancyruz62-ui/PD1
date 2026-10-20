export default function InjectionAngle({ state, floating = false }) {
  if (!state || !['injection', 'intervention_injection'].includes(state.phase)) return null;
  const angle = state.angle;
  const assessable = angle?.fresh && angle.calibrated && angle.calibration_id && angle.angle_deg != null;
  return <aside className={`injection-angle ${floating ? 'floating-angle' : ''} ${assessable && angle.within_target ? 'angle-valid' : ''}`} aria-label="Live syringe angle">
    <span className="eyebrow">{state.phase === 'injection' ? 'INITIAL ANESTHESIA INJECTION' : 'INTERVENTION INJECTION'}</span>
    <div className="angle-number">{assessable ? Number(angle.angle_deg).toFixed(1) : '—'}<small>°</small></div>
    <strong>{!assessable ? 'Waiting for calibrated reading' : angle.within_target ? 'Within prototype target' : 'Outside prototype target'}</strong>
    <p>Target {state.catalog.angle_min_deg}°–{state.catalog.angle_max_deg}° · {state.input_source === 'simulation' ? 'SIMULATED' : 'ESP32'}</p>
    <p>Latest raw: {angle?.raw_angle_deg == null ? '—' : `${Number(angle.raw_angle_deg).toFixed(1)}°`} · smoothed display</p>
    {angle?.error && <p role="status">{angle.error}</p>}
    {state.intervention_policy?.demo_only && state.phase === 'intervention_injection' && <span className="badge">SIMULATION EXERCISE · ROUTE NOT CLINICALLY APPROVED</span>}
    <p className="notice">Confirm completion after performing the injection.</p>
  </aside>;
}
