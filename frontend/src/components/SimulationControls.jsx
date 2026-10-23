import { modeNames, phaseNames } from '../lib/assessmentView';
import { ChevronRight } from 'lucide-react';
import { getNextStep } from '../lib/navigation';

export function formatDuration(seconds) {
  return `${Math.floor(seconds/60).toString().padStart(2,'0')}:${Math.floor(seconds%60).toString().padStart(2,'0')}`;
}

export default function SimulationControls({ state, patient, busy, connected, onAction, onNavigate }) {
  if (!state?.mode) return null;
  const next = getNextStep(state);
  const action = state.phase === 'preparation' ? state.mode === 'full' ? ['begin_injection', 'Begin Initial Injection'] : ['start_scenario', 'Start Scenario'] : state.phase === 'injection' ? ['complete_injection', 'Complete Initial Injection'] : state.phase === 'intervention_injection' ? ['complete_injection', 'Complete Intervention Injection'] : state.phase === 'intervention_non_injectable' ? ['complete_non_injectable_intervention', 'Confirm Intervention Completed'] : null;
  return <div className="simulation-bar"><div className="simulation-summary"><span className="eyebrow">STUDENT {state.student} · {modeNames[state.mode]}</span><strong>{patient.Name}<small>{phaseNames[state.phase]}</small></strong></div><span className="session-timer" aria-label="Assessment elapsed time">{formatDuration(state.elapsed)}</span>
    {next && onNavigate && <button className="secondary next-step-link" title={next.description} aria-label={`Next step: ${next.title}`} onClick={() => onNavigate(next.panel)}><span><small>Next step</small><strong>{next.title}</strong></span><ChevronRight size={18} aria-hidden="true"/></button>}
    {action && <button className="primary" disabled={busy || !connected} onClick={() => onAction(action[0])}>{action[1]}</button>}
    <button className="secondary end-simulation" disabled={busy || !connected} onClick={() => onAction('end')}>End Assessment</button>
  </div>;
}
