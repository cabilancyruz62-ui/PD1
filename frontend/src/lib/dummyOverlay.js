// Use confirmed backend milestones, never raw angle samples or RFID feedback.
export function getDummyPose(state) {
  if (!['full', 'direct'].includes(state?.mode) || ![
    'preparation', 'injection', 'scenario_pending', 'scenario_active',
    'intervention_injection', 'intervention_non_injectable', 'intervention_review', 'evaluated',
  ].includes(state.phase)) return null;
  if (state.phase === 'evaluated' && state.checklist?.drug && state.checklist?.intervention_completion) return 'standing';
  if (state.mode === 'direct' || state.checklist?.initial_injection) return 'lying';
  return 'standing';
}
