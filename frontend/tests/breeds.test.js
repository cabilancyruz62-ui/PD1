import test from 'node:test';
import assert from 'node:assert/strict';
import { Box3, PerspectiveCamera, Vector3 } from 'three';
import { breeds, getBreedProfile } from '../src/data/breeds.js';
import { patients } from '../src/data/patients.js';
import { createBreedPlacements, defaultPlacement } from '../src/lib/dogPlacement.js';
import { createDogModel } from '../src/lib/dogModel.js';
import { frameModelCamera } from '../src/lib/modelFraming.js';

test('every assigned patient has an exact supported model and independent placement', () => {
  const placements = createBreedPlacements(), second = createBreedPlacements();
  assert.equal(new Set(breeds.map(breed => breed.id)).size, 3);
  assert.equal(new Set(breeds.map(breed => breed.modelPath)).size, 3);
  for (const patient of patients) {
    const profile = getBreedProfile(patient.breedId);
    assert.equal(profile.id, patient.breedId);
    assert.equal(profile.label, patient.Breed);
    assert.ok(placements[profile.id]);
  }
  placements.labrador.yaw = 80; placements.beagle.size = 60;
  assert.equal(placements.beagle.yaw, defaultPlacement.yaw);
  assert.equal(placements.dalmatian.yaw, defaultPlacement.yaw);
  assert.equal(placements.labrador.size, defaultPlacement.size);
  for (const placement of Object.values(second)) assert.deepEqual(placement, defaultPlacement);
});

test('inspector framing keeps each breed inside portrait and landscape viewports', () => {
  for (const profile of breeds) {
    const dog = createDogModel(profile);
    for (const pose of [0, 1]) {
      dog.setPose(pose);
      const bounds = new Box3().setFromObject(dog.group, true);
      const size = bounds.getSize(new Vector3());
      size.multiplyScalar(3 / Math.max(size.x, size.y, size.z));
      for (const aspect of [.4, .7, 1, 1.8, 3]) {
        const camera = new PerspectiveCamera(38, aspect, .01, 100);
        frameModelCamera(camera, size);
        for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
          const corner = new Vector3(x * size.x / 2, y * size.y / 2, z * size.z / 2).project(camera);
          assert.ok(Math.abs(corner.x) < 1 && Math.abs(corner.y) < 1, `${profile.id} cropped at aspect ${aspect}`);
          assert.ok(corner.z > -1 && corner.z < 1);
        }
      }
    }
    dog.dispose();
  }
});
