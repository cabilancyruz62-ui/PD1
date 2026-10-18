import { modeNames, phaseNames } from '../lib/assessmentView';

export function formatDuration(seconds) {
  return `${Math.floor(seconds/60).toString().padStart(2,'0')}:${Math.floor(seconds%60).toString().padStart(2,'0')}`;
}

export default function SimulationControls({ state, patient, busy, connected, onAction }) {
  if (!state?.mode) return null;
  const action = state.phase === 'preparation' ? state.mode === 'full' ? ['begin_injection', 'Begin Initial Injection'] : ['start_scenario', 'Start Scenario'] : state.phase === 'injection' ? ['complete_injection', 'Complete Initial Injection'] : state.phase === 'intervention_injection' ? ['complete_injection', 'Complete Intervention Injection'] : state.phase === 'intervention_non_injectable' ? ['complete_non_injectable_intervention', 'Confirm Intervention Completed'] : null;
  return <div className="simulation-bar"><div><span className="eyebrow">STUDENT {state.student} · {modeNames[state.mode]}</span><strong>{patient.Name}<small>{phaseNames[state.phase]}</small></strong></div><span className="session-timer">{formatDuration(state.elapsed)}</span>
    {action && <button className="primary" disabled={busy || !connected} onClick={() => onAction(action[0])}>{action[1]}</button>}
    <button className="secondary end-simulation" disabled={busy || !connected} onClick={() => onAction('end')}>End Assessment</button>
  </div>;
}
