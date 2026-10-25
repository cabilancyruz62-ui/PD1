// Fictional profiles; backend randomizes among these three patient IDs.
export const patients = [
  { id: 'patient_chihuahua', breedId: 'chihuahua', Name: 'Bella', Breed: 'Chihuahua', Age: '3 years', Sex: 'Female', Weight: '3 kg', 'Procedure type': 'Dentistry', Procedure: 'Dental cleaning', Condition: 'Stable · simulated patient' },
  { id: 'patient_golden', breedId: 'golden_retriever', Name: 'Charlie', Breed: 'Golden Retriever', Age: '7 years', Sex: 'Male', Weight: '25 kg', 'Procedure type': 'Surgery', Procedure: 'Mass removal', Condition: 'Senior patient · simulated' },
  { id: 'patient_saint', breedId: 'saint_bernard', Name: 'Spot', Breed: 'Saint Bernard', Age: '4 years', Sex: 'Male', Weight: '65 kg', 'Procedure type': 'Surgery', Procedure: 'Wound repair', Condition: 'Stable · simulated patient' },
];

// Keep names and profile details available for assessments saved before this limit.
const archivedPatients = [
  // Historical assessments keep their original dog breeds when patient pools change.
  { id: 'bella', Name: 'Bella', Breed: 'Labrador Retriever', Age: '3 years', Sex: 'Female', Weight: '24 kg', Procedure: 'Dental cleaning', Condition: 'Stable · simulated patient' },
  { id: 'charlie', Name: 'Charlie', Breed: 'Beagle', Age: '7 years', Sex: 'Male', Weight: '12 kg', Procedure: 'Mass removal', Condition: 'Senior patient · simulated' },
  { id: 'spot', Name: 'Spot', Breed: 'Dalmatian', Age: '4 years', Sex: 'Male', Weight: '22 kg', Procedure: 'Wound repair', Condition: 'Stable · simulated patient' },
  { id: 'max', Name: 'Max', Breed: 'Golden Retriever', Age: '5 years', Sex: 'Male', Weight: '25 kg', Procedure: 'General Anesthesia', Condition: 'Stable · simulated patient' },
  { id: 'luna', Name: 'Luna', Breed: 'Shih Tzu', Age: '4 years', Sex: 'Female', Weight: '6 kg', Procedure: 'Dental examination', Condition: 'Anxious · simulated patient' },
  { id: 'cooper', Name: 'Cooper', Breed: 'German Shepherd', Age: '6 years', Sex: 'Male', Weight: '32 kg', Procedure: 'Orthopedic examination', Condition: 'Stable · simulated patient' },
  { id: 'daisy', Name: 'Daisy', Breed: 'Poodle', Age: '2 years', Sex: 'Female', Weight: '9 kg', Procedure: 'Spay', Condition: 'Stable · simulated patient' },
  { id: 'milo', Name: 'Milo', Breed: 'Aspin', Age: '4 years', Sex: 'Male', Weight: '16 kg', Procedure: 'Wound repair', Condition: 'Alert · simulated patient' },
  { id: 'coco', Name: 'Coco', Breed: 'Dachshund', Age: '8 years', Sex: 'Female', Weight: '8 kg', Procedure: 'Diagnostic imaging', Condition: 'Senior patient · simulated' },
  { id: 'rocky', Name: 'Rocky', Breed: 'Siberian Husky', Age: '3 years', Sex: 'Male', Weight: '22 kg', Procedure: 'Neuter', Condition: 'Stable · simulated patient' },
  { id: 'nala', Name: 'Nala', Breed: 'Border Collie', Age: '5 years', Sex: 'Female', Weight: '18 kg', Procedure: 'Laceration repair', Condition: 'Alert · simulated patient' },
];

const patientLookup = new Map([...archivedPatients, ...patients].map(patient => [patient.id, patient]));

export function getPatientById(id) {
  return patientLookup.get(id);
}

export function randomPatientId(currentId, random = Math.random) {
  const candidates = patients.filter(patient => patient.id !== currentId);
  return candidates[Math.floor(random() * candidates.length)].id;
}
