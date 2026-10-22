import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { patients, getPatientById, randomPatientId } from '../src/data/patients.js';
import { getVitalsState } from '../src/lib/vitals.js';

test('three complete patient profiles use the supported demonstration breeds', () => {
  assert.equal(patients.length, 3);
  assert.equal(new Set(patients.map(p => p.id)).size, 3);
  assert.deepEqual(patients.map(({ id, breedId, Breed }) => ({ id, breedId, Breed })), [
    { id: 'bella', breedId: 'labrador', Breed: 'Labrador Retriever' },
    { id: 'charlie', breedId: 'beagle', Breed: 'Beagle' },
    { id: 'spot', breedId: 'dalmatian', Breed: 'Dalmatian' },
  ]);
  for (const patient of patients) {
    for (const key of ['Name','Breed','Age','Sex','Weight','Procedure','Condition']) assert.ok(patient[key]);
  }
});

test('frontend profiles match the backend assignment pool', () => {
  const config = JSON.parse(readFileSync(new URL('../../backend/config/assessment.json', import.meta.url), 'utf8'));
  assert.deepEqual(config.patient_ids, patients.map(patient => patient.id));
});

test('random assignment selects only active profiles and excludes the current patient', () => {
  const activeIds = new Set(patients.map(patient => patient.id));
  for (const currentId of [...activeIds, 'max', undefined]) {
    for (const fraction of [0, 0.25, 0.5, 0.75, 0.999]) {
      const assigned = randomPatientId(currentId, () => fraction);
      assert.ok(activeIds.has(assigned));
      assert.notEqual(assigned, currentId);
    }
  }
});

test('inactive patients remain available by ID for historical report names', () => {
  const historical = {
    max: ['Max', 'Golden Retriever'], luna: ['Luna', 'Shih Tzu'],
    cooper: ['Cooper', 'German Shepherd'], daisy: ['Daisy', 'Poodle'],
    milo: ['Milo', 'Aspin'], coco: ['Coco', 'Dachshund'],
    rocky: ['Rocky', 'Siberian Husky'], nala: ['Nala', 'Border Collie'],
  };
  for (const [id, [name, breed]] of Object.entries(historical)) {
    const patient = getPatientById(id);
    assert.equal(patient.Name, name);
    assert.equal(patient.Breed, breed);
    assert.equal(patients.some(active => active.id === id), false);
  }
  for (const active of patients) assert.equal(getPatientById(active.id), active);
  assert.equal(getPatientById('unknown-patient'), undefined);
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
