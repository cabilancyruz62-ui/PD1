export const trackingModes = [
  { id: 'normal', label: 'Normal — manual placement' },
  { id: 'aruco', label: 'Design 1 — ArUco marker' },
  { id: 'orb', label: 'Design 2 — ORB + RANSAC' },
  { id: 'optical-flow', label: 'Design 3 — Optical flow' },
];
export const TRACKING_MAX_AGE_MS = 750;
export const trackingModeKey = 'pupvitals.trackingMode';
export function normalizeTrackingMode(value) {
  return trackingModes.some(mode => mode.id === value) ? value : 'normal';
}
export function defaultTrackingAlignment(mode) {
  return { scale: mode === 'aruco' ? 5 : 1.8, offsetX: 0, offsetY: 0, rotation: 0 };
}
export function hasFreshTarget(result, mode, cameraKey, now) {
  return Boolean(result && result.design === mode && result.cameraKey === cameraKey
    && result.status === 'tracking' && now >= result.capturedAt
    && now - result.capturedAt <= TRACKING_MAX_AGE_MS
    && result.frame?.width > 0 && result.frame?.height > 0
    && Array.isArray(result.corners) && result.corners.length === 4
    && result.corners.every(point => Array.isArray(point) && point.length === 2
      && point.every(Number.isFinite) && point[0] >= 0 && point[1] >= 0
      && point[0] < result.frame.width && point[1] < result.frame.height));
}
// Match the video element's centered object-fit: cover, before mirroring the
// entire tracked layer together with the video. Crop offsets can be negative.
export function projectTracking(result, viewport, placement, alignment) {
  const { width, height } = viewport;
  if (!width || !height || !result?.corners) return null;
  const scale = Math.max(width / result.frame.width, height / result.frame.height);
  const left = (width - result.frame.width * scale) / 2;
  const top = (height - result.frame.height * scale) / 2;
  const corners = result.corners.map(([x, y]) => [left + x * scale, top + y * scale]);
  const edge = Math.hypot(corners[1][0] - corners[0][0], corners[1][1] - corners[0][1]);
  if (edge < 1) return null;
  const angle = Math.atan2(corners[1][1] - corners[0][1], corners[1][0] - corners[0][0]);
  const center = corners.reduce((sum, point) => [sum[0] + point[0] / 4, sum[1] + point[1] / 4], [0, 0]);
  const dx = alignment.offsetX * edge, dy = alignment.offsetY * edge;
  return { corners, placement: { ...placement,
    x: (center[0] + Math.cos(angle) * dx - Math.sin(angle) * dy) / width * 100,
    y: (center[1] + Math.sin(angle) * dx + Math.cos(angle) * dy) / height * 100,
    size: edge * alignment.scale / width * 100,
    rotation: angle * 180 / Math.PI + alignment.rotation,
  } };
}

export async function captureTrackingFrame(video) {
  if (!video || video.readyState < 2 || !video.videoWidth || !video.videoHeight) return null;
  const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  const capturedAt = performance.now();
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85));
  if (!blob) throw Error('Could not read a camera frame. Reconnect the camera.');
  return { blob, width: canvas.width, height: canvas.height, capturedAt };
}
