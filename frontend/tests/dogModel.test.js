import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createDogModel } from '../src/lib/dogModel.js';
import { breeds } from '../src/data/breeds.js';

const profiles = breeds;

test('three dog silhouettes have finite, grounded geometry throughout their poses', () => {
  for (const profile of profiles) {
    const model = createDogModel(profile);
    for (const blend of [0, .25, .5, .75, 1]) {
      model.setPose(blend);
      const bounds = new THREE.Box3().setFromObject(model.group, true);
      assert.ok([...bounds.min.toArray(), ...bounds.max.toArray()].every(Number.isFinite));
      assert.ok(bounds.min.y >= -1e-5, `${profile.id} intersects the floor at ${blend}`);
      assert.ok(bounds.min.y < .04, `${profile.id} floats at ${blend}`);
      assert.ok(bounds.max.x - bounds.min.x > 4);
      assert.ok(bounds.max.y < 3.5);
      model.group.traverse(item => {
        if (!item.isMesh) return;
        for (const attribute of ['position', 'normal']) {
          assert.ok(Array.from(item.geometry.getAttribute(attribute).array).every(Number.isFinite), `${item.name} has invalid ${attribute}`);
        }
      });
    }
    model.dispose();
  }
});

test('resting pose lowers the torso and articulates both joints while keeping paws level', () => {
  const model = createDogModel();
  const body = model.group.getObjectByName('dog-body');
  const upper = model.group.getObjectByName('front-near-upper-joint');
  const lower = model.group.getObjectByName('front-near-lower-joint');
  const paw = model.group.getObjectByName('front-near-paw');
  const standingHeight = new THREE.Box3().setFromObject(model.group, true).max.y;
  const standingBody = body.position.y, standingAngle = upper.rotation.z;
  model.setPose(1);
  const restingHeight = new THREE.Box3().setFromObject(model.group, true).max.y;
  assert.ok(body.position.y < standingBody - .7);
  assert.ok(restingHeight < standingHeight - .7);
  assert.ok(Math.abs(upper.rotation.z - standingAngle) > 1);
  assert.ok(lower.rotation.z > 2);
  assert.ok(Math.abs(upper.rotation.z + lower.rotation.z + paw.rotation.z) < 1e-10);
  model.setPose(.5);
  assert.ok(body.position.y > -1 && body.position.y < standingBody);
  model.setPose(0);
  assert.equal(upper.rotation.z, standingAngle);
  model.dispose();
});

test('breed profiles change proportions and coat markings without image assets', () => {
  const labrador = createDogModel(profiles[0]), beagle = createDogModel(profiles[1]), dalmatian = createDogModel(profiles[2]);
  const height = model => new THREE.Box3().setFromObject(model.group, true).max.y;
  assert.ok(height(beagle) < height(labrador));
  assert.ok(height(dalmatian) > height(labrador));
  const colors = model => new Set(Array.from(model.group.getObjectByName('torso').geometry.getAttribute('color').array).map(value => value.toFixed(3)));
  assert.notDeepEqual(colors(beagle), colors(labrador));
  assert.notDeepEqual(colors(dalmatian), colors(labrador));
  assert.ok(beagle.group.getObjectByName('forehead-blaze'));
  assert.ok(dalmatian.group.getObjectByName('front-near-leg-spot'));
  assert.equal(labrador.group.getObjectByName('forehead-blaze'), undefined);
  [labrador, beagle, dalmatian].forEach(model => model.dispose());
});

test('invalid profile sizes and pose values cannot corrupt model transforms', () => {
  const model = createDogModel({ bodyLength: NaN, bodyHeight: Infinity, legLength: 0, headScale: 100, pattern: 'unknown' });
  assert.equal(model.group.userData.profile.bodyLength, 1);
  assert.equal(model.group.userData.profile.bodyHeight, 1);
  assert.equal(model.group.userData.profile.legLength, .65);
  assert.equal(model.group.userData.profile.headScale, 1.35);
  assert.equal(model.group.userData.profile.pattern, 'solid');
  for (const value of [NaN, Infinity, -5, 10]) {
    model.setPose(value);
    assert.ok(model.group.userData.poseBlend >= 0 && model.group.userData.poseBlend <= 1);
    assert.ok(new THREE.Box3().setFromObject(model.group, true).min.toArray().every(Number.isFinite));
  }
  model.dispose();
});

test('dispose releases every owned geometry/material once and detaches the model', () => {
  const model = createDogModel(profiles[2]), parent = new THREE.Group(); parent.add(model.group);
  const resources = new Map();
  model.group.traverse(item => {
    if (!item.isMesh) return;
    for (const resource of [item.geometry, item.material]) {
      if (resources.has(resource)) continue;
      resources.set(resource, 0);
      resource.addEventListener('dispose', () => resources.set(resource, resources.get(resource) + 1));
    }
  });
  model.dispose(); model.dispose(); model.setPose(1);
  assert.equal(model.group.parent, null);
  assert.ok(resources.size > 20);
  assert.ok([...resources.values()].every(count => count === 1));
  assert.equal(model.group.userData.poseBlend, 0);
});
