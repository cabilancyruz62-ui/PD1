import { test } from 'node:test';
import assert from 'node:assert/strict';
import { patients, randomPatientId } from '../src/data/patients.js';
import { getVitalsState } from '../src/lib/vitals.js';

test('ten complete patients and random selection excludes the current one', () => {
  assert.equal(patients.length, 10);
  assert.equal(new Set(patients.map(p => p.id)).size, 10);
  for (const patient of patients) {
    for (const key of ['Name','Breed','Age','Sex','Weight','Procedure','Condition']) assert.ok(patient[key]);
    for (let i = 0; i < 9; i++) assert.notEqual(randomPatientId(patient.id, () => i / 9), patient.id);
  }
});

test('disabled trigger always allows baseline vitals', () => {
  assert.equal(getVitalsState({ triggerEnabled: false, source: 'esp32' }).active, true);
});

test('simulated wire gates vitals without hardware', () => {
  for (const connected of [false, true]) assert.equal(getVitalsState({ triggerEnabled: true, source: 'simulation', simulatedConnected: connected }).active, connected);
});

test('hardware mode rejects simulation, missing, disconnected, and stale signals', () => {
  const input = { triggerEnabled: true, source: 'esp32', simulatedConnected: true, now: 10000, receivedAt: 9000 };
  assert.equal(getVitalsState(input).active, false);
  const wire = { source: 'esp32', fresh: true, connected: true };
  assert.equal(getVitalsState({ ...input, wire }).active, true);
  assert.equal(getVitalsState({ ...input, wire: { ...wire, connected: false } }).active, false);
  assert.equal(getVitalsState({ ...input, wire: { ...wire, fresh: false } }).active, false);
  assert.equal(getVitalsState({ ...input, wire: { ...wire, source: 'simulation' } }).active, false);
  assert.equal(getVitalsState({ ...input, wire, now: 12000 }).active, false);
  assert.equal(getVitalsState({ ...input, wire, receivedAt: 0 }).active, false);
});
