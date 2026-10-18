export const modeNames = { full: 'Option 1 · Full procedure + scenario', direct: 'Option 2 · Direct scenario' };
export const phaseNames = { mode_selection: 'Choose assessment mode', preparation: 'Baseline / preparation', injection: 'Initial anesthesia injection', scenario_pending: 'Displaying complication', scenario_active: 'Awaiting RFID intervention', intervention_injection: 'Drug verified · intervention injection', intervention_non_injectable: 'Verified non-injectable intervention', intervention_review: 'Intervention route awaiting veterinary review', evaluated: 'Intervention completed · results ready', ended: 'Assessment ended', interrupted: 'Interrupted by backend restart' };

export function assessmentChecklist(state) {
  const tasks = [['patient', 'Review the assigned patient']];
  const modern = Boolean(state.intervention_policy);
  if (state.mode === 'full') tasks.push([modern ? 'initial_angle' : 'angle', 'Assess the initial anesthesia angle'], [modern ? 'initial_injection' : 'injection', 'Confirm initial anesthesia injection completion']);
  tasks.push(['recognition', 'Recognize the complication'], ['drug', 'Submit the matching registered RFID intervention']);
  if (modern) {
    if (state.intervention_policy.requires_injection) tasks.push(['intervention_angle', 'Assess the intervention injection angle']);
    if (state.intervention_policy.requires_expert_review) tasks.push(['route_review', 'Obtain veterinary approval for the intervention route']);
    tasks.push(['intervention_completion', state.intervention_policy.requires_injection ? 'Confirm intervention injection completion' : 'Confirm approved intervention completion']);
  }
  return tasks.map(([id,label]) => ({ id,label,done: Boolean(state.checklist[id]) }));
}

export function scenarioName(state, id = state.scenario_id) {
  return id ? state.catalog.scenarios[id]?.name || id : 'Baseline · no active complication';
}

export function formatSeconds(value) {
  return value == null ? 'Not submitted' : `${Number(value).toFixed(2)} s`;
}
