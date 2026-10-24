import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultPlacement } from '../src/lib/dogPlacement.js';
import { defaultTrackingAlignment, hasFreshTarget, normalizeTrackingMode, projectTracking } from '../src/lib/tracking.js';

const result = () => ({ design: 'aruco', cameraKey: 'camera-a', status: 'tracking', capturedAt: 1000,
  frame: { width: 640, height: 480 }, corners: [[200, 140], [300, 140], [300, 240], [200, 240]] });

test('normal remains the default and only the four supported choices are accepted', () => {
  for (const value of [null, '', 'invalid', 'design1']) assert.equal(normalizeTrackingMode(value), 'normal');
  for (const value of ['normal', 'aruco', 'orb', 'optical-flow']) assert.equal(normalizeTrackingMode(value), value);
});

test('only fresh results from the current design and camera enable target visibility', () => {
  const target = result();
  assert.equal(hasFreshTarget(target, 'aruco', 'camera-a', 1200), true);
  assert.equal(hasFreshTarget(target, 'aruco', 'camera-a', 1751), false);
  assert.equal(hasFreshTarget(target, 'aruco', 'camera-a', 999), false);
  assert.equal(hasFreshTarget(target, 'orb', 'camera-a', 1200), false);
  assert.equal(hasFreshTarget(target, 'aruco', 'camera-b', 1200), false);
  for (const status of ['searching', 'lost', 'needs_selection', 'error']) {
    assert.equal(hasFreshTarget({ ...target, status }, 'aruco', 'camera-a', 1200), false);
  }
  for (const corners of [null, [], [[NaN, 0], [0, 0], [1, 1], [0, 1]], [[-1, 0], [0, 0], [1, 1], [0, 1]]]) {
    assert.equal(hasFreshTarget({ ...target, corners }, 'aruco', 'camera-a', 1200), false);
  }
});

test('projection follows object-fit cover cropping in landscape and portrait', () => {
  const target = result(), before = structuredClone(defaultPlacement);
  const alignment = { scale: 2, offsetX: 0, offsetY: 0, rotation: 0 };
  const wide = projectTracking(target, { width: 1280, height: 720 }, defaultPlacement, alignment);
  assert.deepEqual(wide.corners, [[400, 160], [600, 160], [600, 360], [400, 360]]);
  assert.equal(wide.placement.x, 500 / 1280 * 100);
  assert.equal(wide.placement.size, 400 / 1280 * 100);
  const portrait = projectTracking(target, { width: 480, height: 960 }, defaultPlacement, alignment);
  assert.deepEqual(portrait.corners, [[0, 280], [200, 280], [200, 480], [0, 480]]);
  assert.deepEqual(defaultPlacement, before);
});

test('alignment offsets rotate and scale with the target, preserving breed viewing controls', () => {
  const target = result();
  target.corners = [[300, 140], [300, 240], [200, 240], [200, 140]];
  const projected = projectTracking(target, { width: 640, height: 480 },
    { ...defaultPlacement, yaw: 24, pitch: 12 }, { scale: 3, offsetX: 1, offsetY: 0, rotation: 15 });
  assert.equal(projected.placement.rotation, 105);
  assert.equal(projected.placement.y, 290 / 480 * 100);
  assert.equal(projected.placement.yaw, 24);
  assert.equal(projected.placement.pitch, 12);
  assert.equal(defaultTrackingAlignment('aruco').scale, 5);
  assert.equal(defaultTrackingAlignment('orb').scale, 1.8);
});
