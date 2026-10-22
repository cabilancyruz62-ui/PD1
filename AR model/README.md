# Blender sources

Keep original `.blend` files here. The initial supported breeds are Labrador Retriever, Beagle, and Dalmatian. Start with one shared rig, then adjust proportions and materials for each breed.

Export `labrador.glb`, `beagle.glb`, and `dalmatian.glb` into `frontend/public/models/` for the rotatable inspector. The website already includes built-in models and runs without these files. The camera overlay currently uses the procedural rig; final GLB rig and tracking integration remain separate work.

See [dog model conventions](../docs/DOG_MODELS.md).
