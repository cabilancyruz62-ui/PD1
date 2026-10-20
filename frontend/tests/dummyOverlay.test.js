import test from 'node:test';
import assert from 'node:assert/strict';
import { getDummyPose } from '../src/lib/dummyOverlay.js';

test('full procedure stands before confirmed anesthesia and lies through drug verification', () => {
  const state = { mode: 'full', phase: 'preparation', checklist: {} };
  assert.equal(getDummyPose(state), 'standing');
  state.phase = 'injection';
  state.checklist.initial_angle = true;
  assert.equal(getDummyPose(state), 'standing', 'valid angle does not complete injection');
  state.checklist.initial_injection = true;
  for (const phase of ['scenario_pending', 'scenario_active', 'intervention_injection', 'intervention_non_injectable', 'intervention_review']) {
    state.phase = phase;
    assert.equal(getDummyPose(state), 'lying');
    state.checklist.drug = true;
    assert.equal(getDummyPose(state), 'lying', 'correct RFID alone does not cause recovery');
  }
  state.phase = 'evaluated';
  assert.equal(getDummyPose(state), 'lying', 'completion still required');
  state.checklist.intervention_completion = true;
  assert.equal(getDummyPose(state), 'standing');
});

test('direct mode starts lying and recovers only after correct intervention completion', () => {
  const state = { mode: 'direct', phase: 'preparation', checklist: {} };
  assert.equal(getDummyPose(state), 'lying');
  state.phase = 'scenario_active';
  state.attempts = [{ correct: false }];
  assert.equal(getDummyPose(state), 'lying', 'wrong or unknown RFID does not cause recovery');
  state.checklist.drug = true;
  state.phase = 'intervention_injection';
  state.checklist.intervention_angle = true;
  assert.equal(getDummyPose(state), 'lying');
  state.checklist.intervention_completion = true;
  state.phase = 'evaluated';
  assert.equal(getDummyPose(state), 'standing');
  state.checklist.drug = false;
  assert.equal(getDummyPose(state), 'lying', 'completion without correct drug is insufficient');
});

test('end, interruption and mode selection hide the dog even with old completion flags', () => {
  for (const mode of ['full', 'direct']) for (const phase of ['ended', 'interrupted', 'mode_selection']) {
    assert.equal(getDummyPose({ mode, phase, checklist: { drug: true, intervention_completion: true } }), null);
  }
  assert.equal(getDummyPose(null), null);
  assert.equal(getDummyPose({ phase: 'preparation' }), null);
  assert.equal(getDummyPose({ mode: 'full', phase: 'unknown' }), null);
});
