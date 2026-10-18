import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createSimulation, simulationReducer as reduce, simulatedVitals, waveSpec, waveSample, monitorChannels } from '../src/lib/simulation.js';

test('patient is locked during a simulation and changes only on end', () => {
  let state = createSimulation('max');
  assert.equal(reduce(state, { type: 'end', nextPatientId: 'luna' }).patientId, 'max');
  state = reduce(state, { type: 'start' });
  state = reduce(state, { type: 'scenario', value: 'slow' });
  state = reduce(state, { type: 'tick', dt: 1, monitorReady: true });
  state = reduce(state, { type: 'selectPatient', value: 'luna' });
  assert.equal(state.patientId, 'max');
  const next = reduce(state, { type: 'end', nextPatientId: 'luna' });
  assert.equal(next.patientId, 'luna');
  assert.equal(next.status, 'ready');
  assert.equal(next.student, 2);
  assert.equal(next.lastReport.patientId, 'max');
  assert.equal(next.lastReport.student, 1);
  assert.deepEqual(next.completed, {});
  assert.deepEqual(next.events, []);
  assert.equal(next.monitored, 0);
  assert.equal(reduce(next, { type: 'end', nextPatientId: 'bella' }), next);
});

test('ending cannot assign the same patient, even if passed an invalid next ID', () => {
  const running = reduce(createSimulation('max'), { type: 'start' });
  for (const nextPatientId of ['max', 'missing', undefined]) {
    assert.notEqual(reduce(running, { type: 'end', nextPatientId }).patientId, 'max');
  }
});

test('wire pause prevents monitor progress and auto scenario changes', () => {
  let state = reduce(createSimulation('max'), { type: 'start' });
  for (let i=0; i<40; i++) state = reduce(state, { type: 'tick', dt: 1, monitorReady: false });
  assert.equal(state.monitored, 0);
  assert.equal(state.scenario, 'stable');
  assert.equal(state.completed.monitor, undefined);
  for (let i=0; i<30; i++) state = reduce(state, { type: 'tick', dt: 1, monitorReady: true });
  assert.equal(state.scenario, 'slow');
  assert.equal(state.completed.monitor, true);
  assert.equal(state.patientId, 'max');
});

test('feedback records actions; checklist only completes actual recorded tasks', () => {
  let state = reduce(createSimulation('max'), { type: 'start' });
  state = reduce(state, { type: 'intervention', value: '  ' });
  assert.equal(state.completed.intervention, undefined);
  state = reduce(state, { type: 'review' });
  state = reduce(state, { type: 'drug', value: 'Propofol' });
  state = reduce(state, { type: 'scenario', value: 'slow' });
  state = reduce(state, { type: 'recognize', value: 'slow', monitorReady: false });
  assert.equal(state.completed.recognition, undefined);
  state = reduce(state, { type: 'tick', dt: 1, monitorReady: true });
  state = reduce(state, { type: 'recognize', value: 'exaggerated', monitorReady: true });
  assert.equal(state.completed.recognition, undefined);
  state = reduce(state, { type: 'recognize', value: 'slow', monitorReady: true });
  state = reduce(state, { type: 'intervention', value: 'Reported the monitor change to the instructor.' });
  const next = reduce(state, { type: 'end', nextPatientId: 'bella' });
  assert.ok(next.lastReport.checklist.every(task => task.done));
  assert.ok(next.lastReport.events.some(event => event.text.includes('Propofol')));
  assert.ok(next.lastReport.events.some(event => event.text.includes('Reported the monitor change')));
  assert.equal(next.completed.drug, undefined);
});

test('wave rate and amplitude respond to low and exaggerated simulated parameters', () => {
  const normal = simulatedVitals('max', 0), low = simulatedVitals('max', 0, 'slow'), high = simulatedVitals('max', 0, 'exaggerated');
  assert.ok(waveSpec('rr', low).rate < waveSpec('rr', normal).rate);
  assert.ok(waveSpec('rr', low).amplitude < waveSpec('rr', normal).amplitude);
  assert.ok(waveSpec('rr', high).amplitude > waveSpec('rr', normal).amplitude);
  assert.ok(waveSpec('hr', high).rate > waveSpec('hr', normal).rate);
  assert.ok(waveSpec('map', high).amplitude > waveSpec('map', normal).amplitude);
  assert.ok(waveSpec('etco2', low).amplitude > waveSpec('etco2', normal).amplitude);
  assert.ok(waveSpec('spo2', low).amplitude < waveSpec('spo2', normal).amplitude);
  assert.equal(waveSpec('rr', { ...normal, rr: 0 }).rate, 0);
  assert.equal(waveSpec('temp', high).rate, 3);
  for (const channel of monitorChannels) {
    for (let i=0;i<100;i++) assert.ok(Number.isFinite(waveSample(channel.key,i/100)));
  }
});

test('manual values override simulated drift without changing patient or assessment', () => {
  const values = simulatedVitals('max', 50, 'stable', { rr: 0, hr: 140, temp: 39.2 });
  assert.equal(values.rr, 0);
  assert.equal(values.hr, 140);
  assert.equal(values.temp, 39.2);
  assert.notDeepEqual(simulatedVitals('max', 0), simulatedVitals('luna', 0));
  let state = reduce(createSimulation('max'), { type: 'start' });
  state = reduce(state, { type: 'override', key: 'rr', value: 8 });
  assert.equal(state.auto, false);
  assert.equal(state.patientId, 'max');
  assert.equal(state.completed.recognition, undefined);
});
