# Three user-provided canine GLB assets — automatically assigned breeds

This patch replaces the old procedural dog renderer (and the earlier one-file `canine.glb` patch) with the user's three distinct 3D assets. **There is no breed selection menu.** The backend randomly selects one of three fictional patient profiles for the next assessment and avoids immediately repeating the previous patient. The assigned `patient_id` remains unchanged for that assessment, so the displayed breed and 3D model match throughout.

| Assigned breed | Required exact GLB filename | Frontend route |
| --- | --- | --- |
| Chihuahua | `Chihuahua.glb` | `/models/Chihuahua.glb` |
| Golden Retriever | `Golden Retriever Dog.glb` | `/models/Golden%20Retriever%20Dog.glb` |
| Saint Bernard | `Saint Bernard Dog.glb` | `/models/Saint%20Bernard%20Dog.glb` |

Place **all three** files in `frontend/public/models/`. Do not rename them to `canine.glb`. Filenames are case-sensitive on some operating systems. **The GLB binary files are not included** because only screenshots of filenames were provided.

## Patient assignment

Backend configuration `backend/config/assessment.json` uses `patient_ids` `patient_chihuahua`, `patient_golden`, and `patient_saint`. The backend randomizes which patient is prepared for each new assessment, excluding the previous patient's ID. The frontend's patient profiles map those IDs to the correct breed and GLB, including the AR overlay and Settings > 3D Patient inspection. No manual breed selector is added. Randomization happens when the backend prepares a new patient, **not on every page refresh**.

The existing name, age, sex, procedure and condition attributes are retained. Illustrative body weights were changed to 3 kg, 25 kg and 65 kg so the example profiles are consistent with the displayed breeds. These are fictional example profiles—not veterinary guidance or validated medication-dosing references; your veterinarian/client should review them before assessed use.

Previously saved reports using the former IDs `bella`, `charlie`, `spot` resolve to their original Labrador, Beagle and Dalmatian descriptions, rather than being silently relabeled. Their *3D* procedural models are not reintroduced.

## AR, animations, and performance

Both the Settings viewer and the existing manual / ArUco / ORB + RANSAC / Optical Flow camera overlays load the breed-matched GLB. If a file is missing, an error will appear; no procedural fallback dog is generated. Each new breed triggers its own model load. The existing scene normalization supports models from different sources; it does not guarantee veterinary anatomical calibration. Animations play only if the corresponding clips actually exist in each GLB.

Large 40–45 MB models may take noticeably longer to load; optimize textures/mesh in Blender as needed. The current tracking modes are primarily screen-space placement, not calibrated full 3D registration.
