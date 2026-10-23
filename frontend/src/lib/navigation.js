export function getNextStep(state) {
  if (!state?.mode) return null;
  switch (state.phase) {
    case 'preparation':
      return state.checklist?.patient
        ? { panel: 'scenario', title: 'Choose scenario', description: 'Choose the complication and start this exercise.' }
        : { panel: 'patient', title: 'Review patient', description: 'Read the assigned patient information.' };
    case 'injection':
      return { panel: 'scenario', title: 'Check injection angle', description: 'Check the angle, then confirm the initial injection.' };
    case 'scenario_pending':
      return { panel: 'vitals', title: 'Review vitals', description: 'Watch the vital signs as the complication starts.' };
    case 'scenario_active':
      return state.checklist?.recognition
        ? { panel: 'hardware', title: 'Scan drug tag', description: 'Scan an RFID tag or use the hardware test controls.' }
        : { panel: 'assessment', title: 'Identify complication', description: 'Review the vitals and record the complication in the checklist.' };
    case 'intervention_injection':
      return { panel: 'scenario', title: 'Complete intervention', description: 'Check the new injection angle and confirm intervention completion.' };
    case 'intervention_non_injectable':
      return { panel: 'scenario', title: 'Confirm intervention', description: 'Confirm completion of the verified non-injectable intervention.' };
    case 'intervention_review':
      return { panel: 'scenario', title: 'View intervention status', description: 'The intervention route is awaiting veterinary approval.' };
    case 'evaluated':
    case 'ended':
    case 'interrupted':
      return { panel: 'assessment', title: 'View post feedback', description: 'Review the completed checklist and assessment report.' };
    default:
      return { panel: 'assessment', title: 'View checklist', description: 'Check the remaining assessment tasks.' };
  }
}
