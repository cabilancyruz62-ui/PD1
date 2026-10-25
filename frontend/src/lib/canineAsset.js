import * as THREE from 'three';
import { getBreedProfile } from '../data/breeds.js';

// Match the randomly assigned patient breed in both the inspector and the AR overlay.
export function getCanineModelPath(breedId) {
  return getBreedProfile(breedId).modelPath;
}

// Wrap instead of editing the imported GLB transforms: its bones/animations remain intact.
export function centerAndScaleCanine(scene, targetLength = 3) {
  const bounds = new THREE.Box3().setFromObject(scene);
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const longest = Math.max(size.x, size.y, size.z);
  if (bounds.isEmpty() || !Number.isFinite(longest) || longest <= 0) {
    throw new Error('The GLB has no valid visible geometry');
  }
  const scale = targetLength / longest;
  const wrapper = new THREE.Group();
  wrapper.name = 'your-canine-glb';
  wrapper.add(scene);
  wrapper.scale.setScalar(scale);
  wrapper.position.copy(center).multiplyScalar(-scale);
  return { wrapper, size: size.multiplyScalar(scale) };
}

export function getCanineClip(animations = [], pose = 'standing') {
  const matcher = pose === 'lying'
    ? /lie|lying|lay|down|rest|sleep|sedat|recumbent/i
    : /stand|idle|breath|neutral/i;
  const exact = animations.find(clip => matcher.test(clip.name));
  // Use a generic single clip as the inspector/standing preview only. Do not
  // claim that an unnamed animation represents a lying-down position.
  return exact || (pose === 'standing' ? animations[0] || null : null);
}

export function disposeCanineScene(scene) {
  if (!scene) return;
  const geometries = new Set(), materials = new Set(), textures = new Set();
  scene.traverse(node => {
    if (node.geometry) geometries.add(node.geometry);
    const entries = node.material ? (Array.isArray(node.material) ? node.material : [node.material]) : [];
    for (const material of entries) {
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    }
  });
  for (const texture of textures) texture.dispose();
  for (const material of materials) material.dispose();
  for (const geometry of geometries) geometry.dispose();
}

export function describeCanineLoadError(error, modelPath) {
  if (error?.message?.includes('valid visible geometry')) return error.message;
  return `Unable to load ${decodeURI(modelPath || '')}. Check that the matching GLB is present in frontend/public/models/ and refresh the page.`;
}
