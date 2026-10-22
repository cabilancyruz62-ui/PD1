import { breeds } from '../data/breeds.js';

export const defaultPlacement = { x: 65, y: 57, size: 45, rotation: 0, yaw: 0, pitch: 0, opacity: 80 };

export function createBreedPlacements() {
  return Object.fromEntries(breeds.map(breed => [breed.id, { ...defaultPlacement }]));
}
