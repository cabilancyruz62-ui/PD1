import { modeNames, phaseNames, scenarioName, formatSeconds } from '../lib/assessmentView';

export default function ScenarioPanel({ state, command, disabled }) {
  if (!state?.mode) return <p className="notice">Choose an assessment mode first.</p>;
  const preparing = state.phase === 'preparation';
  return <><span className="badge">{modeNames[state.mode]}</span><dl className="detail-list"><div><dt>Status</dt><dd>{phaseNames[state.phase]}</dd></div><div><dt>Active complication</dt><dd>{scenarioName(state)}</dd></div><div><dt>Visible since</dt><dd>{state.scenario_started_at ? new Date(state.scenario_started_at).toLocaleTimeString() : 'Not started'}</dd></div><div><dt>First intervention</dt><dd>{formatSeconds(state.first_response_seconds)}</dd></div></dl>
    <label className="field">Scenario for this assessment<select disabled={disabled || !preparing} value={state.planned_scenario} onChange={e => command('configure', { scenario_id: e.target.value })}>{Object.entries(state.catalog.scenarios).map(([id,scenario]) => <option key={id} value={id}>{scenario.name}</option>)}</select></label>
    {state.mode === 'direct' && preparing && <p className="notice">Starting updates the monitor to the selected complication.</p>}
    <p className="notice">{state.mode === 'full' ? 'Begin injection, check the angle, then confirm completion.' : 'Review vitals and start the scenario. Verify the drug, then complete the intervention.'}</p>
    {state.phase === 'preparation' && <button className="primary full-width" disabled={disabled} onClick={() => command(state.mode === 'full' ? 'begin_injection' : 'start_scenario')}>{state.mode === 'full' ? 'Begin Injection' : 'Start Scenario'}</button>}
    {['injection', 'intervention_injection'].includes(state.phase) && <button className="primary full-width" disabled={disabled} onClick={() => command('complete_injection')}>{state.phase === 'injection' ? 'Complete Initial Injection' : 'Complete Intervention Injection'}</button>}
    {state.phase === 'intervention_review' && <p className="backend-required" role="status">Drug verified. This route requires veterinary approval before proceeding.</p>}
    {state.phase === 'intervention_non_injectable' && <button className="primary full-width" disabled={disabled} onClick={() => command('complete_non_injectable_intervention')}>Confirm Non-injectable Intervention Completed</button>}
    <div className="connection-card"><div><strong>Intervention exercise</strong><small>Record the complication, scan the drug tag, then complete the intervention.</small></div></div>
    <p className="notice">Training drugs only. Clinical interventions require veterinary approval.</p>
  </>;
}
