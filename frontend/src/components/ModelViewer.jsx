import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { breeds, getBreedProfile } from '../data/breeds.js';
import { createDogModel } from '../lib/dogModel.js';
import { frameModelCamera } from '../lib/modelFraming.js';

function disposeModel(model) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  model?.traverse(node => {
    if (node.geometry) geometries.add(node.geometry);
    const entries = node.material ? (Array.isArray(node.material) ? node.material : [node.material]) : [];
    for (const material of entries) {
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    }
  });
  textures.forEach(texture => texture.dispose());
  materials.forEach(material => material.dispose());
  geometries.forEach(geometry => geometry.dispose());
}

export default function ModelViewer({ breedId = 'labrador' }) {
  const host = useRef(null);
  const [previewBreed, setPreviewBreed] = useState(breedId);
  const breed = getBreedProfile(previewBreed);
  const [message, setMessage] = useState('Loading 3D dog…');
  useEffect(() => { setPreviewBreed(breedId); }, [breedId]);
  useEffect(() => {
    const element = host.current;
    let active = true, renderer, controls, builtIn, imported, mixer, frame, resize;
    const scene = new THREE.Scene(), clock = new THREE.Clock();
    setMessage(`Built-in ${breed.label} model`);
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      element.appendChild(renderer.domElement);
      const camera = new THREE.PerspectiveCamera(38, 1, .01, 100);
      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.minDistance = 2;
      controls.maxDistance = 14;
      scene.add(new THREE.HemisphereLight(0xfff6e6, 0x344b46, 2));
      const light = new THREE.DirectionalLight(0xfff0dc, 3.2); light.position.set(-3, 5, 6); scene.add(light);
      const rim = new THREE.DirectionalLight(0xdcefff, 1.8); rim.position.set(3, 3, -4); scene.add(rim);
      const display = new THREE.Group(); scene.add(display);
      let displaySize = new THREE.Vector3(3, 2, 1);
      function fitCamera() {
        Object.assign(controls, frameModelCamera(camera, displaySize));
        controls.target.set(0, 0, 0); controls.update();
      }
      function present(model) {
        const bounds = new THREE.Box3().setFromObject(model);
        const size = bounds.getSize(new THREE.Vector3()), center = bounds.getCenter(new THREE.Vector3());
        if (bounds.isEmpty() || !Number.isFinite(size.length()) || size.length() === 0) throw new Error('Empty 3D model');
        model.position.sub(center);
        const wrapper = new THREE.Group(); wrapper.add(model);
        const scale = 3 / Math.max(size.x, size.y, size.z);
        wrapper.scale.setScalar(scale); displaySize = size.clone().multiplyScalar(scale);
        display.clear(); display.add(wrapper);
        camera.position.set(-.3, .7, 5.2); fitCamera();
      }
      builtIn = createDogModel(breed);
      builtIn.setPose(0); present(builtIn.group);
      resize = new ResizeObserver(() => {
        const w = Math.max(element.clientWidth, 1), h = Math.max(element.clientHeight, 1);
        camera.aspect = w / h; fitCamera(); renderer.setSize(w, h);
      });
      resize.observe(element);
      new GLTFLoader().load(breed.modelPath, gltf => {
        if (!active) { disposeModel(gltf.scene); return; }
        try {
          present(gltf.scene); imported = gltf.scene;
          builtIn.dispose(); builtIn = null;
          if (gltf.animations.length) {
            mixer = new THREE.AnimationMixer(imported); mixer.clipAction(gltf.animations[0]).play();
          }
          setMessage(`Blender ${breed.label} model`);
        } catch {
          disposeModel(gltf.scene);
          setMessage(`Built-in ${breed.label} model`);
        }
      }, undefined, () => { /* The built-in dog remains visible while Blender assets are absent. */ });
      function render() { frame = requestAnimationFrame(render); controls.update(); mixer?.update(clock.getDelta()); renderer.render(scene, camera); }
      render();
    } catch { setMessage('3D rendering is unavailable in this browser'); }
    return () => {
      active = false; cancelAnimationFrame(frame); resize?.disconnect(); controls?.dispose();
      mixer?.stopAllAction(); if (imported) mixer?.uncacheRoot(imported);
      builtIn?.dispose(); disposeModel(imported); renderer?.dispose(); renderer?.domElement.remove();
    };
  }, [breed]);
  return <>
    <label className="field">Inspect a breed<select value={breed.id} onChange={event => setPreviewBreed(event.target.value)}>{breeds.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
    <div className="model-canvas" ref={host} aria-label={`Interactive ${breed.label} model`}/>
    <p className="notice" role="status">{message}. Drag to rotate · scroll to zoom.</p>
    <p className="notice">Inspection only. The camera overlay follows the assigned patient's breed.</p>
  </>;
}
