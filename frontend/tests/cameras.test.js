import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createCameraRegistry, cameraOptionLabel } from '../src/lib/cameras.js';

const camera = (deviceId, label = '') => ({ kind: 'videoinput', deviceId, label });

test('camera choices retain the browser ID while presenting friendly hexadecimal IDs', () => {
  const registry = createCameraRegistry();
  const devices = registry.list([camera('browser-built-in', 'Integrated Webcam'), camera('browser-usb', 'USB Camera'), { kind: 'audioinput', deviceId: 'microphone' }]);
  assert.equal(devices.length, 2);
  assert.equal(cameraOptionLabel(devices[0]), '0x001 — Integrated Webcam');
  assert.equal(cameraOptionLabel(devices[1]), '0x002 — USB Camera');
  assert.equal(devices[1].deviceId, 'browser-usb');
  assert.equal(devices[1].selectable, true);
});

test('reordering, hotplugging and reconnecting never assign an old ID to another camera', () => {
  const registry = createCameraRegistry();
  registry.list([camera('a'), camera('b')]);
  const changed = registry.list([camera('b', 'USB Camera'), camera('c', 'New Camera')]);
  assert.equal(changed[0].appId, '0x002');
  assert.equal(changed[1].appId, '0x003');
  const reconnected = registry.list([camera('a'), camera('c')]);
  assert.equal(reconnected[0].appId, '0x001');
  assert.equal(reconnected[1].appId, '0x003');
});

test('permission-hidden devices are not given a fake selectable browser ID', () => {
  const registry = createCameraRegistry();
  const [hidden] = registry.list([camera('')]);
  assert.equal(hidden.appId, null);
  assert.equal(hidden.selectable, false);
  assert.equal(hidden.deviceId, '');
  assert.equal(cameraOptionLabel(hidden), 'Permission needed — Camera name hidden');
  assert.equal(registry.list([camera('allowed')])[0].appId, '0x001');
});

test('labels can be revealed later without changing IDs; duplicate device entries are removed', () => {
  const registry = createCameraRegistry();
  const first = registry.list([camera('a')]);
  const second = registry.list([camera('a', 'USB Webcam'), camera('a', 'USB Webcam')]);
  assert.equal(first[0].appId, second[0].appId);
  assert.equal(second.length, 1);
  assert.equal(second[0].label, 'USB Webcam');
  assert.deepEqual(registry.list(undefined), []);
});
