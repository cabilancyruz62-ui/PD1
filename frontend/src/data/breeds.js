// Three user-provided GLB models; breed is chosen automatically by the assessment backend.
// Keep filenames exactly as shown in your Windows file list (including spaces/case).
export const breeds = [
  { id: 'chihuahua', label: 'Chihuahua', modelPath: '/models/Chihuahua.glb' },
  { id: 'golden_retriever', label: 'Golden Retriever', modelPath: '/models/Golden%20Retriever%20Dog.glb' },
  { id: 'saint_bernard', label: 'Saint Bernard', modelPath: '/models/Saint%20Bernard%20Dog.glb' },
];

export function getBreedProfile(id) {
  return breeds.find(breed => breed.id === id) || breeds[0];
}
