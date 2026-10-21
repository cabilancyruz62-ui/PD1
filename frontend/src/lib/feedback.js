const injectionPhases = new Set(['injection', 'intervention_injection']);
const activePhases = new Set([
  'preparation', 'injection', 'scenario_pending', 'scenario_active',
  'intervention_injection', 'intervention_non_injectable', 'intervention_review',
]);
const scoredResults = new Set(['incorrect', 'unregistered', 'correct']);
const finiteNumber = value => typeof value === 'number' && Number.isFinite(value);
const nonemptyString = value => typeof value === 'string' && value.trim().length > 0;
const validAngle = value => finiteNumber(value) && value >= 0 && value <= 90;

export function getAngleFeedback(state) {
  if (!injectionPhases.has(state?.phase)) return null;

  const waiting = message => ({ status: 'waiting', title: 'Waiting for calibrated reading', message, value: null });
  const minimum = state.catalog?.angle_min_deg;
  const maximum = state.catalog?.angle_max_deg;
  if (!validAngle(minimum) || !validAngle(maximum) || minimum > maximum) {
    return waiting('Waiting for a valid configured angle target.');
  }

  const angle = state.angle;
  if (!angle || angle.fresh !== true || angle.calibrated !== true || !nonemptyString(angle.calibration_id)
    || !nonemptyString(state.injection_stage_id) || angle.injection_stage_id !== state.injection_stage_id
    || !validAngle(angle.angle_deg) || !validAngle(angle.raw_angle_deg)) {
    return waiting('Waiting for a fresh calibrated angle reading for this injection.');
  }

  const raw = angle.raw_angle_deg;
  const smoothed = angle.angle_deg;
  const target = `Target ${minimum}°–${maximum}°.`;
  const classify = value => value < minimum ? 'low' : value > maximum ? 'high' : 'valid';
  const rawStatus = classify(raw);
  // The backend requires both readings to pass. Prioritize a new excursion even
  // while smoothing still shows an earlier, acceptable reading.
  const status = rawStatus === 'valid' ? classify(smoothed) : rawStatus;
  const value = rawStatus === 'valid' ? smoothed : raw;
  if (status !== 'valid') {
    const title = `Angle too ${status}`;
    const reading = raw === smoothed ? `${value.toFixed(1)}°`
      : rawStatus !== 'valid' ? `${raw.toFixed(1)}° latest reading (smoothed ${smoothed.toFixed(1)}°)`
        : `${smoothed.toFixed(1)}° smoothed reading (latest reading ${raw.toFixed(1)}°)`;
    return { status, title, message: `${title}: ${reading}. ${target}`, value };
  }
  if (angle.within_target !== true) {
    return {
      status: 'outside', title: 'Outside prototype target',
      message: `Angle has not passed the prototype target check. ${target}`, value,
    };
  }
  return {
    status: 'valid', title: 'Within prototype target',
    message: `Angle within prototype target: ${smoothed.toFixed(1)}°. ${target}`, value,
  };
}

export function getDrugFeedback(state) {
  if (!['full', 'direct'].includes(state?.mode) || !activePhases.has(state?.phase)
    || !nonemptyString(state?.scenario_id) || state.checklist?.drug === true) return null;

  const attempts = Array.isArray(state.attempts) ? state.attempts : [];
  const attempt = attempts.findLast(item => item?.scenario_id === state.scenario_id && scoredResults.has(item.result));
  if (!attempt || attempt.result === 'correct') return null;

  const scenario = state.catalog?.scenarios?.[state.scenario_id]?.name || state.scenario_id;
  if (attempt.result === 'unregistered') {
    return {
      status: 'unknown', title: 'Unregistered RFID tag',
      message: `Unregistered RFID tag for ${scenario}. Scan a registered drug tag.`,
    };
  }
  if (!nonemptyString(attempt.drug?.name)) {
    return {
      status: 'unknown', title: 'Drug not identified',
      message: `Drug not identified for ${scenario}. Scan a registered drug tag.`,
    };
  }
  return {
    status: 'wrong', title: 'Wrong drug',
    message: `Wrong drug: ${attempt.drug.name.trim()} for ${scenario}.`,
  };
}
