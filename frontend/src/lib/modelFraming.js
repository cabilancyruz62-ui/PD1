import { MathUtils, Vector3 } from 'three';

// Fit a centered bounding sphere to both the horizontal and vertical field of view.
export function frameModelCamera(camera, size) {
  const radius = Math.max(size.length() / 2, .01);
  const vertical = MathUtils.degToRad(camera.fov);
  const horizontal = 2 * Math.atan(Math.tan(vertical / 2) * Math.max(camera.aspect, .01));
  const distance = radius / Math.sin(Math.min(vertical, horizontal) / 2) * 1.12;
  const direction = camera.position.lengthSq() > 0 ? camera.position.clone().normalize() : new Vector3(-.06, .14, 1).normalize();
  camera.position.copy(direction.multiplyScalar(distance));
  camera.near = .01;
  camera.far = Math.max(100, distance * 8);
  camera.lookAt(0, 0, 0);
  camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  return { minDistance: radius * 1.2, maxDistance: distance * 4 };
}
