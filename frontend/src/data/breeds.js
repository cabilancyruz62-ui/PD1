// Relative visual proportions for a shared rig, not measured anatomy or physical calibration.
export const breeds = [
  { id: 'labrador', label: 'Labrador Retriever', modelPath: '/models/labrador.glb', pattern: 'solid', coat: 0xc79c60, darkCoat: 0x65422e, lightCoat: 0xf3e8d4, bodyLength: 1, bodyHeight: 1, legLength: 1, muzzleLength: 1, earLength: 1, headScale: 1 },
  { id: 'beagle', label: 'Beagle', modelPath: '/models/beagle.glb', pattern: 'tricolor', coat: 0xad6b34, darkCoat: 0x282723, lightCoat: 0xf4efe5, bodyLength: .92, bodyHeight: .94, legLength: .84, muzzleLength: .9, earLength: 1.15, headScale: .93 },
  { id: 'dalmatian', label: 'Dalmatian', modelPath: '/models/dalmatian.glb', pattern: 'spots', coat: 0xf1eee6, darkCoat: 0x242526, lightCoat: 0xf9f6ef, bodyLength: 1.03, bodyHeight: .98, legLength: 1.1, muzzleLength: 1.05, earLength: .88, headScale: .98 },
];

export function getBreedProfile(id) {
  return breeds.find(breed => breed.id === id) || breeds[0];
}
