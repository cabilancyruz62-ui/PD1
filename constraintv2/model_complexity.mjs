import { mkdir, stat, writeFile } from 'node:fs/promises';
import { dirname, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { REVISION } from '../frontend/node_modules/three/build/three.module.js';
import { createDogModel } from '../frontend/src/lib/dogModel.js';
import { breeds } from '../frontend/src/data/breeds.js';

const repositoryRoot = fileURLToPath(new URL('../', import.meta.url));
const localPath = value => relative(repositoryRoot, value).replaceAll('\\', '/');

function nonnegativeInteger(value, label) {
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(`${label} must be a nonnegative integer`);
  return value;
}

function drawCount(geometry, group = null) {
  const available = geometry.index?.count ?? geometry.getAttribute('position').count;
  const range = geometry.drawRange;
  const start = Math.max(0, range.start, group?.start ?? 0);
  const end = Math.min(available, range.start + range.count, group ? group.start + group.count : Infinity);
  return Math.max(0, end - start);
}

/**
 * Count triangle topology available to one visible scene pass. This performs no
 * rendering or frustum/occlusion culling. Hidden ancestors/materials, geometry
 * draw ranges, material groups, shared geometries and InstancedMesh are handled.
 * Vertex counts are position-attribute entries, including duplicated seam data;
 * they are not welded spatial vertices or an estimate of GPU memory.
 */
export function measureScene(root) {
  const geometries = new Set();
  const materials = new Set();
  const totals = {
    mesh_count: 0,
    visible_mesh_count: 0,
    mesh_instance_count: 0,
    visible_mesh_instance_count: 0,
    indexed_mesh_count: 0,
    nonindexed_mesh_count: 0,
    unique_geometry_count: 0,
    unique_material_count: 0,
    stored_vertex_count: 0,
    instance_vertex_count: 0,
    visible_instance_vertex_count: 0,
    stored_index_count: 0,
    triangle_count: 0,
    indexed_triangle_count: 0,
    nonindexed_triangle_count: 0,
  };

  function visit(object, ancestorsVisible) {
    const visible = ancestorsVisible && object.visible !== false;
    if (object.isMesh) {
      const geometry = object.geometry;
      const positions = geometry?.getAttribute('position');
      if (!positions) throw new Error(`Mesh ${object.name || '(unnamed)'} has no position attribute`);
      nonnegativeInteger(positions.count, 'Position attribute count');
      const instances = object.isInstancedMesh ? nonnegativeInteger(object.count, 'Instance count') : 1;
      totals.mesh_count += 1;
      totals.mesh_instance_count += instances;
      totals.instance_vertex_count += positions.count * instances;
      totals[geometry.index ? 'indexed_mesh_count' : 'nonindexed_mesh_count'] += 1;
      if (!geometries.has(geometry)) {
        geometries.add(geometry);
        totals.stored_vertex_count += positions.count;
        totals.stored_index_count += geometry.index?.count ?? 0;
      }
      const allMaterials = Array.isArray(object.material) ? object.material : [object.material];
      allMaterials.filter(Boolean).forEach(material => materials.add(material));
      let trianglesPerInstance = 0;
      if (visible) {
        if (Array.isArray(object.material)) {
          for (const group of geometry.groups) {
            if (object.material[group.materialIndex]?.visible) trianglesPerInstance += Math.floor(drawCount(geometry, group) / 3);
          }
        } else if (object.material?.visible) {
          trianglesPerInstance = Math.floor(drawCount(geometry) / 3);
        }
      }
      if (trianglesPerInstance > 0 && instances > 0) {
        totals.visible_mesh_count += 1;
        totals.visible_mesh_instance_count += instances;
        totals.visible_instance_vertex_count += positions.count * instances;
      }
      const triangles = trianglesPerInstance * instances;
      totals.triangle_count += triangles;
      totals[geometry.index ? 'indexed_triangle_count' : 'nonindexed_triangle_count'] += triangles;
    }
    for (const child of object.children || []) visit(child, visible);
  }

  visit(root, true);
  totals.unique_geometry_count = geometries.size;
  totals.unique_material_count = materials.size;
  return totals;
}

async function inspectConfiguredAsset(modelPath) {
  const absolutePath = resolve(repositoryRoot, 'frontend/public', modelPath.replace(/^\//, ''));
  try {
    const info = await stat(absolutePath);
    return {
      configured_url: modelPath,
      file: localPath(absolutePath),
      present: info.isFile(),
      size_bytes: info.isFile() ? info.size : null,
      used_by_current_dog_renderer: false,
      triangle_count: null,
      reason: info.isFile()
        ? 'Asset exists but the current DummyOverlay renderer creates the procedural model; imported GLB topology is not measured by this script.'
        : 'Configured asset path is not a regular file; the current renderer uses the procedural model.',
    };
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    return {
      configured_url: modelPath,
      file: localPath(absolutePath),
      present: false,
      size_bytes: null,
      used_by_current_dog_renderer: false,
      triangle_count: null,
      reason: 'No GLB asset is supplied at the configured path; the current renderer uses the procedural model.',
    };
  }
}

export async function measureModels() {
  const models = [];
  for (const breed of breeds) {
    const dog = createDogModel(breed);
    try {
      dog.setPose(0);
      const standing = measureScene(dog.group);
      dog.setPose(1);
      const lying = measureScene(dog.group);
      models.push({
        breed_id: breed.id,
        breed_label: breed.label,
        model_type: 'procedural_visual_stand_in',
        blender_asset: false,
        poses: { standing, lying },
        topology_stable_between_poses: JSON.stringify(standing) === JSON.stringify(lying),
        configured_glb: await inspectConfiguredAsset(breed.modelPath),
      });
    } finally {
      dog.dispose();
    }
  }
  return {
    schema_version: 1,
    measurement_kind: 'static_model_complexity',
    generated_at_utc: new Date().toISOString(),
    three_revision: REVISION,
    model_source: 'frontend/src/lib/dogModel.js',
    profile_source: 'frontend/src/data/breeds.js',
    renderer_source: 'frontend/src/components/DummyOverlay.jsx',
    triangle_unit: 'triangles',
    polygon_count: null,
    polygon_count_reason: 'The models use triangulated BufferGeometry. Original authored polygon or quad counts cannot be inferred from triangle indices.',
    scope: 'One visible canine model before camera frustum or occlusion culling; model geometry only, not lights, camera, tracking graphics or multiple GPU render passes.',
    count_definitions: {
      triangle_count: 'Sum of floor(drawable index or nonindexed position count / 3) per visible mesh/material group, multiplied by InstancedMesh.count when applicable.',
      stored_vertex_count: 'Sum of position-attribute entry counts over unique mesh geometries, including seam duplicates and hidden mesh geometry.',
      instance_vertex_count: 'Sum of complete position-attribute entry counts per mesh instance, including hidden mesh instances; this is not a count of vertices processed by the GPU.',
      visible_instance_vertex_count: 'Complete position-attribute entry counts per visible mesh instance that contributes triangles; not reduced for draw ranges or culling.',
      mesh_count: 'Scene graph mesh objects; InstancedMesh remains one object and its instances are counted separately.',
      stored_index_count: 'Index-buffer element counts over unique geometries; these are indices, not vertices or triangles.',
    },
    limitations: [
      'Static geometry measurement; no browser, WebGL frame timing, runtime memory, or GPU performance is measured.',
      'Triangle totals do not remove back-facing, degenerate, hidden-by-other-geometry or off-camera triangles.',
      'Wireframe mode, shadow passes, multi-view rendering, LOD selection and non-mesh primitives are outside this measurement.',
      'Current canine models are procedural approximations; repeat the measurement for fitted Blender/GLB assets when those are integrated.',
    ],
    models,
  };
}

async function main(args) {
  if (args.includes('--help')) {
    process.stdout.write('Usage: node constraintv2/model_complexity.mjs [--output PATH]\nWrites measured canine model complexity as JSON. No renderer or camera is started.\n');
    return;
  }
  let outputPath = null;
  if (args.length) {
    if (args.length !== 2 || args[0] !== '--output' || !args[1]) throw new Error('Expected --output PATH, or no arguments for JSON on stdout');
    outputPath = resolve(args[1]);
  }
  const report = await measureModels();
  const encoded = `${JSON.stringify(report, null, 2)}\n`;
  if (outputPath) {
    await mkdir(dirname(outputPath), { recursive: true });
    await writeFile(outputPath, encoded, 'utf8');
  }
  process.stdout.write(encoded);
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  main(process.argv.slice(2)).catch(error => {
    process.stderr.write(`Model complexity measurement failed: ${error.message}\n`);
    process.exitCode = 1;
  });
}
