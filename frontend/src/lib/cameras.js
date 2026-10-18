// Friendly app identifiers only; the browser deviceId is used to open a camera.
// Keep the registry for the mounted app so unplugging/reordering never reassigns IDs.
export function createCameraRegistry() {
  const identifiers = new Map();
  let next = 1;
  return {
    identify(deviceId) {
      if (!deviceId) return null;
      if (!identifiers.has(deviceId)) identifiers.set(deviceId, `0x${(next++).toString(16).toUpperCase().padStart(3, '0')}`);
      return identifiers.get(deviceId);
    },
    list(devices) {
      const seen = new Set();
      return (devices || []).filter(device => {
        if (device.kind !== 'videoinput') return false;
        if (device.deviceId && seen.has(device.deviceId)) return false;
        if (device.deviceId) seen.add(device.deviceId);
        return true;
      }).map(device => ({
        deviceId: device.deviceId || '',
        label: device.label || '',
        appId: this.identify(device.deviceId),
        selectable: Boolean(device.deviceId),
      }));
    },
  };
}

export function cameraOptionLabel(device) {
  return `${device.appId || 'Permission needed'} — ${device.label || 'Camera name hidden'}`;
}
