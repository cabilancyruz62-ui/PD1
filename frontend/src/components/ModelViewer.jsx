import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { getCanineModelPath, centerAndScaleCanine, disposeCanineScene, getCanineClip, describeCanineLoadError } from '../lib/canineAsset.js';
import { frameModelCamera } from '../lib/modelFraming.js';

export default function ModelViewer({ breedId }) {
  const modelPath = getCanineModelPath(breedId);
  const host = useRef(null);
  const [message, setMessage] = useState('Loading 3D patient…');
  useEffect(() => {
    const element = host.current;
    let active = true, renderer, controls, imported, mixer, frame, resize;
    const scene = new THREE.Scene(), clock = new THREE.Clock();
    setMessage(`Loading ${decodeURI(modelPath)}…`);
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      element.appendChild(renderer.domElement);
      const camera = new THREE.PerspectiveCamera(38, 1, .01, 100);
      camera.position.set(-.3, .7, 5.2);
      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      scene.add(new THREE.HemisphereLight(0xfff6e6, 0x344b46, 2));
      const light = new THREE.DirectionalLight(0xfff0dc, 3.2); light.position.set(-3, 5, 6); scene.add(light);
      const rim = new THREE.DirectionalLight(0xdcefff, 1.8); rim.position.set(3, 3, -4); scene.add(rim);
      const display = new THREE.Group(); scene.add(display);
      let displaySize = new THREE.Vector3(3, 2, 1);
      function fitCamera() {
        Object.assign(controls, frameModelCamera(camera, displaySize));
        controls.target.set(0, 0, 0); controls.update();
      }
      resize = new ResizeObserver(() => {
        const w = Math.max(element.clientWidth, 1), h = Math.max(element.clientHeight, 1);
        camera.aspect = w / h; fitCamera(); renderer.setSize(w, h);
      });
      resize.observe(element);
      new GLTFLoader().load(modelPath, gltf => {
        if (!active) { disposeCanineScene(gltf.scene); return; }
        try {
          const { wrapper, size } = centerAndScaleCanine(gltf.scene);
          imported = gltf.scene;
          display.add(wrapper); displaySize = size;
          fitCamera();
          const clip = getCanineClip(gltf.animations, 'standing');
          if (clip) {
            mixer = new THREE.AnimationMixer(imported);
            mixer.clipAction(clip).play();
          }
          setMessage(clip ? 'Breed-matched GLB loaded · animation preview' : 'Breed-matched GLB loaded · static model');
        } catch (error) {
          disposeCanineScene(gltf.scene);
          setMessage(describeCanineLoadError(error, modelPath));
        }
      }, undefined, error => { if (active) setMessage(describeCanineLoadError(error, modelPath)); });
      function render() { frame = requestAnimationFrame(render); controls.update(); mixer?.update(clock.getDelta()); renderer.render(scene, camera); }
      render();
    } catch { setMessage('3D rendering unavailable. Enable WebGL / hardware acceleration.'); }
    return () => {
      active = false;
      cancelAnimationFrame(frame); resize?.disconnect(); controls?.dispose();
      mixer?.stopAllAction(); if (imported) mixer?.uncacheRoot(imported);
      disposeCanineScene(imported); renderer?.dispose(); renderer?.domElement.remove();
    };
  }, [modelPath]);
  return <>
    <div className="model-canvas" ref={host} aria-label="Interactive preview of the assigned patient breed GLB"/>
    <p className="notice" role="status">{message}</p>
    <p className="notice">Drag to rotate · scroll to zoom. The model automatically matches the patient breed in the camera overlay.</p>
  </>;
}
