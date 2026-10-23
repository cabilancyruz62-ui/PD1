import test from 'node:test';
import assert from 'node:assert/strict';
import { getNextStep } from '../src/lib/navigation.js';

test('both options guide patient review before scenario setup without changing task state', () => {
  for (const mode of ['full', 'direct']) {
    const state = { mode, phase: 'preparation', checklist: { patient: false } };
    const before = structuredClone(state);
    assert.equal(getNextStep(state).panel, 'patient');
    assert.deepEqual(state, before);
    state.checklist.patient = true;
    assert.equal(getNextStep(state).panel, 'scenario');
  }
});

test('active injection navigation stays with the current stage even if patient review was skipped', () => {
  for (const phase of ['injection', 'intervention_injection']) {
    assert.equal(getNextStep({ mode: 'full', phase, checklist: {} }).panel, 'scenario');
  }
});

test('scenario guidance opens vitals, recognition, then hardware in response to actual progress', () => {
  for (const mode of ['full', 'direct']) {
    const state = { mode, phase: 'scenario_pending', checklist: {} };
    assert.equal(getNextStep(state).panel, 'vitals');
    state.phase = 'scenario_active';
    assert.equal(getNextStep(state).panel, 'assessment');
    state.checklist.recognition = true;
    assert.equal(getNextStep(state).panel, 'hardware');
  }
});

test('non-injectable and review routes show their own next step', () => {
  const review = getNextStep({ mode: 'direct', phase: 'intervention_review' });
  assert.equal(review.panel, 'scenario');
  assert.match(review.description, /awaiting veterinary approval/);
  const nonInjectable = getNextStep({ mode: 'direct', phase: 'intervention_non_injectable' });
  assert.equal(nonInjectable.panel, 'scenario');
  assert.match(nonInjectable.description, /non-injectable/);
});

test('finished assessments lead to post feedback and an unselected mode has no active task', () => {
  for (const phase of ['evaluated', 'ended', 'interrupted']) {
    const next = getNextStep({ mode: 'full', phase });
    assert.equal(next.panel, 'assessment');
    assert.equal(next.title, 'View post feedback');
  }
  assert.equal(getNextStep(null), null);
  assert.equal(getNextStep({ mode: null, phase: 'mode_selection' }), null);
});
