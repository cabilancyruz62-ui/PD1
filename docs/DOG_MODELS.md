# Three-breed model setup

The first version assigns only Bella (Labrador Retriever), Charlie (Beagle), and Spot (Dalmatian). The backend and frontend share the same three patient IDs. Previous patient names remain available in historical reports. Restart the backend after updating from the earlier ten-patient version, then refresh the browser.

## Built-in models

The procedural dogs share a rig and coordinate convention, with breed-specific proportions and coat markings:

| Breed | Visual differences |
| --- | --- |
| Labrador Retriever | Yellow coat, broad head and muzzle, sturdy torso |
| Beagle | Tricolor coat, shorter legs, longer hanging ears |
| Dalmatian | White coat with dark spots, longer legs, leaner proportions |

The shared model includes a tapered torso, shaped muzzle, bilateral eyes and ears, paws, articulated limbs, and a curved tail. It supports standing and a folded resting pose while retaining the existing assessment timing. These are visual approximations, not photorealistic scans or anatomical models. A textured Blender mesh remains the path to a more realistic final patient.

Open **Settings > 3D Patient**. **Inspect a breed** changes only the rotatable inspector. The camera overlay follows the assigned patient. Drag the inspector to rotate, and scroll to zoom.

## Alignment

Enable **Preview for alignment** and adjust horizontal/vertical placement, size, screen rotation, left/right turn, tilt, and opacity. Each breed has independent settings for the current page session. **Reset this breed's placement** leaves the other two settings intact. Refreshing resets all placements.

Use the same fixed camera, dummy position, and viewport while tuning each breed. Matching the forelimb's visible length and injection location matters more than the breed label. The relative mesh proportions are not measurements of the physical dummy. This is manual screen alignment; the three standalone OpenCV trackers are not connected to it yet.

## Blender handoff

Place optional exports in `frontend/public/models/` as `labrador.glb`, `beagle.glb`, and `dalmatian.glb`. The inspector loads the selected breed's file and otherwise retains its built-in model. It plays the first exported animation when one exists. The camera overlay currently keeps the procedural rig; imported-rig pose control and physical tracking integration remain future work.

For the final assets, use consistent real-world scale (one exported unit per meter), a shared rig, applied object transforms, and embedded textures. In the exported glTF scene, use Y up, the head toward negative X, and the ground below the body as a consistent origin. Include named forelimb/injection anchors and standing/resting animations. Measure the actual dummy before selecting the final body and limb dimensions. The inspector automatically frames imports, so its on-screen size does not establish physical calibration.

The shared implementation is in `frontend/src/lib/dogModel.js`; appearance profiles are in `frontend/src/data/breeds.js`. Placement defaults live in `frontend/src/lib/dogPlacement.js`. No external dog assets or additional dependencies are required for the built-in models.
