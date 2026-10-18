import { test } from 'node:test';
import assert from 'node:assert/strict';
import { assessmentChecklist, formatSeconds, scenarioName } from '../src/lib/assessmentView.js';
import { waveSpec, waveSample, monitorChannels } from '../src/lib/monitor.js';

test('Option 2 skips initial injection but requires intervention angle and confirmation', () => {
  const direct = assessmentChecklist({ mode: 'direct', checklist: { recognition: true, drug: true }, intervention_policy: { requires_injection: true } });
  assert.equal(direct.some(task => task.id === 'initial_angle' || task.id === 'initial_injection'), false);
  assert.equal(direct.some(task => task.id === 'intervention_angle'), true);
  assert.equal(direct.some(task => task.id === 'intervention_completion'), true);
  assert.equal(direct.find(task => task.id === 'drug').done, true);
  const full = assessmentChecklist({ mode: 'full', checklist: {}, intervention_policy: { requires_injection: true } });
  assert.equal(full.some(task => task.id === 'initial_angle'), true);
  assert.equal(full.some(task => task.id === 'initial_injection'), true);
  assert.equal(full.some(task => task.id === 'intervention_angle'), true);
});

test('non-injectable and unapproved real routes do not display an injection angle task', () => {
  for (const requires_expert_review of [false, true]) {
    const tasks = assessmentChecklist({ mode: 'direct', checklist: {}, intervention_policy: { requires_injection: false, requires_expert_review } });
    assert.equal(tasks.some(task => task.id === 'intervention_angle'), false);
    assert.equal(tasks.some(task => task.id === 'route_review'), requires_expert_review);
  }
});

test('response display preserves a real zero and distinguishes an absent submission', () => {
  assert.equal(formatSeconds(0), '0.00 s');
  assert.equal(formatSeconds(null), 'Not submitted');
  assert.equal(formatSeconds(12.345), '12.35 s');
  assert.equal(scenarioName({ scenario_id: null }), 'Baseline · no active complication');
});

test('distinct monitor traces respond to low respiration, pressure and heart rate', () => {
  const normal = { hr: 90, rr: 20, spo2: 98, map: 90, etco2: 38, temp: 38.5 };
  const low = { ...normal, rr: 6, hr: 45, map: 50, etco2: 55 };
  assert.ok(waveSpec('rr', low).rate < waveSpec('rr', normal).rate);
  assert.ok(waveSpec('rr', low).amplitude < waveSpec('rr', normal).amplitude);
  assert.ok(waveSpec('hr', low).rate < waveSpec('hr', normal).rate);
  assert.ok(waveSpec('map', low).amplitude < waveSpec('map', normal).amplitude);
  assert.ok(waveSpec('etco2', low).amplitude > waveSpec('etco2', normal).amplitude);
  assert.equal(waveSpec('temp', normal).rate, 3);
  for (const channel of monitorChannels) for (let i=0; i<100; i++) assert.ok(Number.isFinite(waveSample(channel.key,i/100)));
});
