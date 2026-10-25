import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { getCanineModelPath, centerAndScaleCanine, getCanineClip, disposeCanineScene } from '../src/lib/canineAsset.js';

test('each patient breed loads the matching custom GLB, not a generated dog', () => {
  assert.equal(getCanineModelPath('chihuahua'), '/models/Chihuahua.glb');
  assert.equal(getCanineModelPath('golden_retriever'), '/models/Golden%20Retriever%20Dog.glb');
  assert.equal(getCanineModelPath('saint_bernard'), '/models/Saint%20Bernard%20Dog.glb');
});

test('centering and scaling a GLB preserves its original object transforms and geometry', () => {
  const scene = new THREE.Group();
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 4), new THREE.MeshBasicMaterial());
  mesh.position.set(5, 2, -3);
  scene.add(mesh);
  const originalPosition = mesh.position.clone();
  const { wrapper, size } = centerAndScaleCanine(scene);
  assert.ok(mesh.position.equals(originalPosition));
  assert.equal(size.z, 3);
  assert.equal(wrapper.children[0], scene);
  const bounds = new THREE.Box3().setFromObject(wrapper);
  const center = bounds.getCenter(new THREE.Vector3());
  assert.ok(center.length() < 1e-6, `model not centered: ${center.toArray()}`);
  assert.throws(() => centerAndScaleCanine(new THREE.Group()), /valid visible geometry/);
  disposeCanineScene(scene);
});

test('lying animation requires a matching named GLB clip', () => {
  const idle = new THREE.AnimationClip('Idle_Breathing', 2, []);
  const rest = new THREE.AnimationClip('Dog_Lying_Down', 2, []);
  assert.equal(getCanineClip([idle, rest], 'standing'), idle);
  assert.equal(getCanineClip([idle, rest], 'lying'), rest);
  assert.equal(getCanineClip([idle], 'lying'), null);
  assert.equal(getCanineClip([], 'standing'), null);
});

test('GLB cleanup disposes shared GPU resources exactly once', () => {
  const scene = new THREE.Group();
  const geo = new THREE.BoxGeometry(1, 1, 1), mat = new THREE.MeshBasicMaterial();
  scene.add(new THREE.Mesh(geo, mat), new THREE.Mesh(geo, mat));
  let geometriesDisposed = 0, materialsDisposed = 0;
  geo.addEventListener('dispose', () => geometriesDisposed++);
  mat.addEventListener('dispose', () => materialsDisposed++);
  disposeCanineScene(scene);
  assert.equal(geometriesDisposed, 1);
  assert.equal(materialsDisposed, 1);
});
