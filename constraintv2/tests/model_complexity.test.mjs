import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../../frontend/node_modules/three/build/three.module.js';
import { breeds } from '../../frontend/src/data/breeds.js';
import { measureModels, measureScene } from '../model_complexity.mjs';

function triangle(indexed = false) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 1, 0, 0, 0, 1, 0], 3));
  if (indexed) geometry.setIndex([0, 1, 2]);
  return geometry;
}

test('shared and instanced geometries count storage once and scene instances separately', () => {
  const root = new THREE.Group();
  const indexed = triangle(true), nonindexed = triangle();
  const material = new THREE.MeshBasicMaterial();
  root.add(new THREE.Mesh(indexed, material), new THREE.Mesh(indexed, material));
  root.add(new THREE.InstancedMesh(nonindexed, material, 4));
  const result = measureScene(root);
  assert.equal(result.mesh_count, 3);
  assert.equal(result.mesh_instance_count, 6);
  assert.equal(result.unique_geometry_count, 2);
  assert.equal(result.unique_material_count, 1);
  assert.equal(result.stored_vertex_count, 6);
  assert.equal(result.instance_vertex_count, 18);
  assert.equal(result.triangle_count, 6);
  assert.equal(result.indexed_triangle_count, 2);
  assert.equal(result.nonindexed_triangle_count, 4);
  indexed.dispose(); nonindexed.dispose(); material.dispose();
});

test('hidden mesh ancestors and materials suppress triangle totals but retain stored geometry', () => {
  const root = new THREE.Group(), hidden = new THREE.Group();
  const geometry = triangle(true), material = new THREE.MeshBasicMaterial();
  hidden.visible = false;
  hidden.add(new THREE.Mesh(geometry, material));
  const invisibleMaterial = material.clone(); invisibleMaterial.visible = false;
  root.add(hidden, new THREE.Mesh(geometry, invisibleMaterial), new THREE.Mesh(geometry, material));
  const result = measureScene(root);
  assert.equal(result.mesh_count, 3);
  assert.equal(result.stored_vertex_count, 3);
  assert.equal(result.instance_vertex_count, 9);
  assert.equal(result.visible_instance_vertex_count, 3);
  assert.equal(result.visible_mesh_count, 1);
  assert.equal(result.triangle_count, 1);
  geometry.dispose(); material.dispose(); invisibleMaterial.dispose();
});

test('draw ranges intersect material groups and invisible material groups are excluded', () => {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(new Array(27).fill(0), 3));
  geometry.setIndex([0, 1, 2, 3, 4, 5, 6, 7, 8]);
  geometry.addGroup(0, 3, 0); geometry.addGroup(3, 6, 1);
  geometry.setDrawRange(3, 3);
  const shown = new THREE.MeshBasicMaterial(), hidden = shown.clone(); hidden.visible = false;
  const mesh = new THREE.Mesh(geometry, [shown, shown]);
  assert.equal(measureScene(mesh).triangle_count, 1);
  mesh.material = [shown, hidden];
  assert.equal(measureScene(mesh).triangle_count, 0);
  mesh.material = shown;
  assert.equal(measureScene(mesh).triangle_count, 1);
  geometry.setDrawRange(20, Infinity);
  assert.equal(measureScene(mesh).triangle_count, 0);
  geometry.dispose(); shown.dispose(); hidden.dispose();
});

test('zero active instances produce no submitted triangles or visible mesh instances', () => {
  const geometry = triangle(true), material = new THREE.MeshBasicMaterial();
  const mesh = new THREE.InstancedMesh(geometry, material, 2); mesh.count = 0;
  const result = measureScene(mesh);
  assert.equal(result.triangle_count, 0);
  assert.equal(result.visible_mesh_instance_count, 0);
  assert.equal(result.mesh_count, 1);
  assert.equal(result.stored_vertex_count, 3);
  geometry.dispose(); material.dispose();
});

test('actual supported canine models have stable pose topology and breed-specific mesh details', async () => {
  const report = await measureModels();
  assert.deepEqual(report.models.map(model => model.breed_id), breeds.map(breed => breed.id));
  assert.equal(report.triangle_unit, 'triangles');
  assert.equal(report.polygon_count, null);
  for (const model of report.models) {
    assert.equal(model.model_type, 'procedural_visual_stand_in');
    assert.equal(model.blender_asset, false);
    assert.equal(model.topology_stable_between_poses, true);
    assert.deepEqual(model.poses.standing, model.poses.lying);
    const pose = model.poses.standing;
    assert.ok(Number.isSafeInteger(pose.triangle_count) && pose.triangle_count > 10000);
    assert.equal(pose.triangle_count, pose.indexed_triangle_count + pose.nonindexed_triangle_count);
    assert.equal(pose.triangle_count * 3, pose.stored_index_count);
    assert.equal(pose.mesh_count, pose.visible_mesh_count);
    assert.equal(pose.mesh_instance_count, pose.mesh_count);
    assert.equal(pose.stored_vertex_count, pose.instance_vertex_count);
    assert.equal(model.configured_glb.used_by_current_dog_renderer, false);
  }
  const byBreed = Object.fromEntries(report.models.map(model => [model.breed_id, model.poses.standing]));
  assert.ok(byBreed.beagle.mesh_count > byBreed.labrador.mesh_count);
  assert.ok(byBreed.dalmatian.mesh_count > byBreed.labrador.mesh_count);
  assert.ok(byBreed.beagle.triangle_count > byBreed.labrador.triangle_count);
  assert.ok(byBreed.dalmatian.triangle_count > byBreed.labrador.triangle_count);
});
