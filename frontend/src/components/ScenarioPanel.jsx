import { modeNames, phaseNames, scenarioName, formatSeconds } from '../lib/assessmentView';

export default function ScenarioPanel({ state, command, disabled }) {
  if (!state?.mode) return <p className="notice">Choose Option 1 or Option 2 to prepare an assessment.</p>;
  const preparing = state.phase === 'preparation';
  return <><span className="badge">{modeNames[state.mode]}</span><dl className="detail-list"><div><dt>Status</dt><dd>{phaseNames[state.phase]}</dd></div><div><dt>Active complication</dt><dd>{scenarioName(state)}</dd></div><div><dt>Visible since</dt><dd>{state.scenario_started_at ? new Date(state.scenario_started_at).toLocaleTimeString() : 'Not started'}</dd></div><div><dt>First intervention</dt><dd>{formatSeconds(state.first_response_seconds)}</dd></div></dl>
    <label className="field">Scenario for this assessment<select disabled={disabled || !preparing} value={state.planned_scenario} onChange={e => command('configure', { scenario_id: e.target.value })}>{Object.entries(state.catalog.scenarios).map(([id,scenario]) => <option key={id} value={id}>{scenario.name}</option>)}</select></label>
    {state.mode === 'direct' && preparing && <p className="notice">Start Scenario immediately changes the simulated monitor to the selected complication: hypotension lowers MAP, hypoventilation lowers RR and raises EtCO₂, and bradycardia lowers HR. The waveforms and heartbeat beep follow these values.</p>}
    <p className="notice">{state.mode === 'full' ? 'Begin Injection, record a fresh calibrated angle, then explicitly confirm Complete Injection. Orientation alone does not confirm administration.' : 'Review baseline vitals, then press Start Scenario. Only the initial anesthesia injection is skipped. After RFID verification, the intervention injection and angle are assessed in this mode too.'}</p>
    {state.phase === 'preparation' && <button className="primary full-width" disabled={disabled} onClick={() => command(state.mode === 'full' ? 'begin_injection' : 'start_scenario')}>{state.mode === 'full' ? 'Begin Injection' : 'Start Scenario'}</button>}
    {['injection', 'intervention_injection'].includes(state.phase) && <button className="primary full-width" disabled={disabled} onClick={() => command('complete_injection')}>{state.phase === 'injection' ? 'Complete Initial Injection' : 'Complete Intervention Injection'}</button>}
    {state.phase === 'intervention_review' && <p className="backend-required" role="status">The placeholder drug was verified, but this real intervention route needs veterinary approval before requiring an injection. End the assessment or configure an approved route for a later session.</p>}
    {state.phase === 'intervention_non_injectable' && <button className="primary full-width" disabled={disabled} onClick={() => command('complete_non_injectable_intervention')}>Confirm Non-injectable Intervention Completed</button>}
    <div className="connection-card"><div><strong>Intervention exercise</strong><small>Identify the active complication in Assessment, then tap a registered RFID-tagged placeholder drug. Use Hardware → Simulation controls until the ESP32 is connected.</small></div></div>
    <p className="notice">Drug 1–3 are exercise identifiers only. Hypoventilation may require airway or ventilation management; clinical interventions must be approved by a licensed veterinary expert.</p>
  </>;
}
