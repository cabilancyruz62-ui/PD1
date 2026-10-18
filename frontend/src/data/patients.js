// Fictional training profiles. Baselines are UI samples, not clinical reference ranges.
export const patients = [
  { id: 'max', Name: 'Max', Breed: 'Golden Retriever', Age: '5 years', Sex: 'Male', Weight: '25 kg', Procedure: 'General Anesthesia', Condition: 'Stable · simulated patient' },
  { id: 'bella', Name: 'Bella', Breed: 'Labrador Retriever', Age: '3 years', Sex: 'Female', Weight: '24 kg', Procedure: 'Dental cleaning', Condition: 'Stable · simulated patient' },
  { id: 'charlie', Name: 'Charlie', Breed: 'Beagle', Age: '7 years', Sex: 'Male', Weight: '12 kg', Procedure: 'Mass removal', Condition: 'Senior patient · simulated' },
  { id: 'luna', Name: 'Luna', Breed: 'Shih Tzu', Age: '4 years', Sex: 'Female', Weight: '6 kg', Procedure: 'Dental examination', Condition: 'Anxious · simulated patient' },
  { id: 'cooper', Name: 'Cooper', Breed: 'German Shepherd', Age: '6 years', Sex: 'Male', Weight: '32 kg', Procedure: 'Orthopedic examination', Condition: 'Stable · simulated patient' },
  { id: 'daisy', Name: 'Daisy', Breed: 'Poodle', Age: '2 years', Sex: 'Female', Weight: '9 kg', Procedure: 'Spay', Condition: 'Stable · simulated patient' },
  { id: 'milo', Name: 'Milo', Breed: 'Aspin', Age: '4 years', Sex: 'Male', Weight: '16 kg', Procedure: 'Wound repair', Condition: 'Alert · simulated patient' },
  { id: 'coco', Name: 'Coco', Breed: 'Dachshund', Age: '8 years', Sex: 'Female', Weight: '8 kg', Procedure: 'Diagnostic imaging', Condition: 'Senior patient · simulated' },
  { id: 'rocky', Name: 'Rocky', Breed: 'Siberian Husky', Age: '3 years', Sex: 'Male', Weight: '22 kg', Procedure: 'Neuter', Condition: 'Stable · simulated patient' },
  { id: 'nala', Name: 'Nala', Breed: 'Border Collie', Age: '5 years', Sex: 'Female', Weight: '18 kg', Procedure: 'Laceration repair', Condition: 'Alert · simulated patient' },
];

export function randomPatientId(currentId, random = Math.random) {
  const candidates = patients.filter(patient => patient.id !== currentId);
  return candidates[Math.floor(random() * candidates.length)].id;
}
