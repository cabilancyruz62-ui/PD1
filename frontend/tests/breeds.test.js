import test from 'node:test';
import assert from 'node:assert/strict';
import { PerspectiveCamera, Vector3 } from 'three';
import { breeds, getBreedProfile } from '../src/data/breeds.js';
import { patients } from '../src/data/patients.js';
import { createBreedPlacements, defaultPlacement } from '../src/lib/dogPlacement.js';
import { frameModelCamera } from '../src/lib/modelFraming.js';
import { getCanineModelPath } from '../src/lib/canineAsset.js';

test('each random patient breed has a matching user-supplied GLB', () => {
  const placements = createBreedPlacements(), second = createBreedPlacements();
  assert.equal(new Set(breeds.map(breed => breed.id)).size, 3);
  assert.equal(new Set(breeds.map(b => b.modelPath)).size, 3);
  assert.deepEqual(breeds.map(b => b.modelPath), ['/models/Chihuahua.glb', '/models/Golden%20Retriever%20Dog.glb', '/models/Saint%20Bernard%20Dog.glb']);
  for (const patient of patients) {
    const profile = getBreedProfile(patient.breedId);
    assert.equal(profile.id, patient.breedId);
    assert.equal(profile.label, patient.Breed);
    assert.ok(placements[profile.id]);
    assert.equal(getCanineModelPath(patient.breedId), profile.modelPath);
  }
  placements.chihuahua.yaw = 80; placements.golden_retriever.size = 60;
  assert.equal(placements.golden_retriever.yaw, defaultPlacement.yaw);
  assert.equal(placements.saint_bernard.yaw, defaultPlacement.yaw);
  assert.equal(placements.chihuahua.size, defaultPlacement.size);
  for (const placement of Object.values(second)) assert.deepEqual(placement, defaultPlacement);
});

test('GLB viewer camera framing fits a typical centered model in all aspect ratios', () => {
  const size = new Vector3(1.5, 2.4, 3);
  for (const aspect of [.4, .7, 1, 1.8, 3]) {
    const camera = new PerspectiveCamera(38, aspect, .01, 100);
    camera.position.set(-.3, .7, 5.2);
    frameModelCamera(camera, size);
    for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
      const corner = new Vector3(x * size.x / 2, y * size.y / 2, z * size.z / 2).project(camera);
      assert.ok(Math.abs(corner.x) < 1 && Math.abs(corner.y) < 1, `cropped at aspect ${aspect}`);
      assert.ok(corner.z > -1 && corner.z < 1);
    }
  }
});
