import test from 'node:test';
import assert from 'node:assert/strict';
import { getAngleFeedback, getDrugFeedback } from '../src/lib/feedback.js';

function angleState(overrides = {}) {
  return {
    phase: 'injection', injection_stage_id: 'initial-1',
    catalog: { angle_min_deg: 15, angle_max_deg: 30 },
    angle: {
      fresh: true, calibrated: true, calibration_id: 'calibration-1',
      injection_stage_id: 'initial-1', angle_deg: 22, raw_angle_deg: 22,
      within_target: true, ...overrides,
    },
  };
}

function drugState(attempts = [], overrides = {}) {
  return {
    mode: 'full', phase: 'scenario_active', scenario_id: 'hypotension', checklist: { drug: false },
    catalog: { scenarios: { hypotension: { name: 'Hypotension' }, bradycardia: { name: 'Bradycardia' } } },
    attempts, ...overrides,
  };
}

const wrong = (name = 'Drug 2', overrides = {}) => ({
  event_id: 'wrong-1', scenario_id: 'hypotension', result: 'incorrect', drug: { name }, ...overrides,
});

test('angle feedback identifies low, high and a finite zero reading', () => {
  for (const [value, status] of [[0, 'low'], [10, 'low'], [45, 'high']]) {
    const feedback = getAngleFeedback(angleState({ angle_deg: value, raw_angle_deg: value, within_target: false }));
    assert.equal(feedback.status, status);
    assert.equal(feedback.title, `Angle too ${status}`);
    assert.equal(feedback.value, value);
    assert.match(feedback.message, new RegExp(`Angle too ${status}: ${value.toFixed(1)}°`));
  }
});

test('angle target boundaries are inclusive and use configured targets', () => {
  for (const value of [15, 30]) {
    assert.equal(getAngleFeedback(angleState({ angle_deg: value, raw_angle_deg: value })).status, 'valid');
  }
  const state = angleState({ angle_deg: 35, raw_angle_deg: 35 });
  state.catalog = { angle_min_deg: 32, angle_max_deg: 40 };
  assert.equal(getAngleFeedback(state).status, 'valid');
  assert.match(getAngleFeedback(state).message, /Target 32°–40°/);
});

test('latest out-of-range reading takes precedence over smoothed readings', () => {
  for (const [raw, smoothed, status] of [[45, 22, 'high'], [5, 22, 'low'], [45, 5, 'high'], [5, 45, 'low']]) {
    const feedback = getAngleFeedback(angleState({ raw_angle_deg: raw, angle_deg: smoothed, within_target: false }));
    assert.equal(feedback.status, status);
    assert.equal(feedback.value, raw);
    assert.match(feedback.message, new RegExp(`${raw.toFixed(1)}° latest reading`));
    assert.match(feedback.message, new RegExp(`smoothed ${smoothed.toFixed(1)}°`));
  }
});

test('an out-of-range smoothed reading still fails when latest raw reading is inside', () => {
  for (const [smoothed, status] of [[10, 'low'], [40, 'high']]) {
    const feedback = getAngleFeedback(angleState({ raw_angle_deg: 22, angle_deg: smoothed, within_target: false }));
    assert.equal(feedback.status, status);
    assert.equal(feedback.value, smoothed);
    assert.match(feedback.message, new RegExp(`${smoothed.toFixed(1)}° smoothed reading`));
    assert.match(feedback.message, /latest reading 22.0°/);
  }
});

test('an explicit failed or absent backend check never becomes a passing message', () => {
  for (const within_target of [false, undefined, null]) {
    const feedback = getAngleFeedback(angleState({ within_target }));
    assert.equal(feedback.status, 'outside');
    assert.match(feedback.message, /has not passed/);
    assert.doesNotMatch(feedback.message, /Angle within/);
  }
});

test('stale, uncalibrated, invalid and wrong-stage angles wait instead of being rated', () => {
  const patches = [
    { fresh: false }, { fresh: undefined }, { calibrated: false }, { calibration_id: null },
    { calibration_id: '' }, { calibration_id: ' ' }, { calibration_id: 123 },
    { injection_stage_id: 'prior-stage' }, { injection_stage_id: null },
    ...['angle_deg', 'raw_angle_deg'].flatMap(key => [null, undefined, '22', NaN, Infinity, -1, 91, false].map(value => ({ [key]: value }))),
  ];
  for (const patch of patches) {
    const feedback = getAngleFeedback(angleState(patch));
    assert.equal(feedback.status, 'waiting', JSON.stringify(patch));
    assert.equal(feedback.value, null);
  }
  const state = angleState();
  state.injection_stage_id = null;
  assert.equal(getAngleFeedback(state).status, 'waiting');
  state.angle = null;
  assert.equal(getAngleFeedback(state).status, 'waiting');
});

test('invalid target configuration never rates a sample', () => {
  for (const catalog of [undefined, {}, { angle_min_deg: null, angle_max_deg: 30 },
    { angle_min_deg: 15, angle_max_deg: '30' }, { angle_min_deg: NaN, angle_max_deg: 30 },
    { angle_min_deg: 40, angle_max_deg: 30 }, { angle_min_deg: 0, angle_max_deg: Infinity }]) {
    assert.equal(getAngleFeedback({ ...angleState(), catalog }).status, 'waiting');
  }
});

test('both injection stages show feedback and a new stage requires its own fresh reading', () => {
  const state = angleState();
  assert.equal(getAngleFeedback(state).status, 'valid');
  state.phase = 'intervention_injection';
  state.injection_stage_id = 'intervention-2';
  assert.equal(getAngleFeedback(state).status, 'waiting');
  state.angle.injection_stage_id = 'intervention-2';
  assert.equal(getAngleFeedback(state).status, 'valid');
});

test('angle feedback is hidden outside injection phases, including completed and interrupted sessions', () => {
  for (const phase of ['mode_selection', 'preparation', 'scenario_active', 'evaluated', 'ended', 'interrupted']) {
    assert.equal(getAngleFeedback({ ...angleState(), phase }), null);
  }
  assert.equal(getAngleFeedback(null), null);
});

test('wrong-drug feedback names the latest scored drug and active scenario in either mode', () => {
  for (const mode of ['full', 'direct']) {
    const feedback = getDrugFeedback(drugState([wrong('Drug 1'), wrong('Drug 2', { event_id: 'wrong-2' })], { mode }));
    assert.deepEqual(feedback, { status: 'wrong', title: 'Wrong drug', message: 'Wrong drug: Drug 2 for Hypotension.' });
  }
});

test('wrong-drug feedback survives dismissing notices, unrelated scans and repeat attempts', () => {
  const state = drugState([wrong()], { notification: null });
  assert.equal(getDrugFeedback(state).status, 'wrong');
  state.notification = { kind: 'ignored', message: 'Unrelated ignored scan' };
  state.attempts.push({ result: 'ignored', scenario_id: 'hypotension', drug: { name: 'Ignored drug' } });
  assert.equal(getDrugFeedback(state).message, 'Wrong drug: Drug 2 for Hypotension.');
  state.attempts.push(wrong('Drug 3', { event_id: 'wrong-2' }));
  assert.equal(getDrugFeedback(state).message, 'Wrong drug: Drug 3 for Hypotension.');
});

test('correct retries and verified checklist clear earlier wrong-drug feedback', () => {
  const state = drugState([wrong()]);
  state.attempts.push({ result: 'correct', scenario_id: 'hypotension', drug: { name: 'Drug 1' } });
  assert.equal(getDrugFeedback(state), null);
  state.attempts = [wrong()];
  state.checklist.drug = true;
  assert.equal(getDrugFeedback(state), null);
});

test('unregistered tags are identified separately without inventing a drug name', () => {
  const feedback = getDrugFeedback(drugState([wrong(), {
    result: 'unregistered', scenario_id: 'hypotension', uid: 'AABB', drug: null,
  }]));
  assert.equal(feedback.status, 'unknown');
  assert.equal(feedback.title, 'Unregistered RFID tag');
  assert.equal(feedback.message, 'Unregistered RFID tag for Hypotension. Scan a registered drug tag.');
  assert.doesNotMatch(feedback.message, /Wrong drug|Drug 2|AABB/);
  assert.equal(getDrugFeedback(drugState([wrong(null)])).status, 'unknown');
});

test('scenario changes and reset cannot display an earlier scenario drug warning', () => {
  const state = drugState([wrong()]);
  state.scenario_id = 'bradycardia';
  assert.equal(getDrugFeedback(state), null);
  state.attempts.push(wrong('Drug 3', { scenario_id: 'bradycardia' }));
  assert.equal(getDrugFeedback(state).message, 'Wrong drug: Drug 3 for Bradycardia.');
  state.attempts = [];
  assert.equal(getDrugFeedback(state), null);
  state.attempts = [wrong()];
  state.scenario_id = null;
  assert.equal(getDrugFeedback(state), null);
});

test('drug feedback is hidden after assessment completion, end, interruption or without a selected mode', () => {
  for (const phase of ['evaluated', 'ended', 'interrupted', 'mode_selection', 'unknown']) {
    assert.equal(getDrugFeedback(drugState([wrong()], { phase })), null);
  }
  assert.equal(getDrugFeedback(drugState([wrong()], { mode: null })), null);
  assert.equal(getDrugFeedback(null), null);
});
