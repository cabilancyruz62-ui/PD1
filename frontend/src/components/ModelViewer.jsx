import { useEffect, useRef, useState } from 'react';
import { Box } from 'lucide-react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

function disposeModel(model) {
  model?.traverse(node => {
    node.geometry?.dispose();
    const materials = node.material ? (Array.isArray(node.material) ? node.material : [node.material]) : [];
    materials.forEach(material => { Object.values(material).forEach(value => { if (value?.isTexture) value.dispose(); }); material.dispose(); });
  });
}

export default function ModelViewer() {
  const host = useRef(null);
  const [message, setMessage] = useState('Loading canine model…');
  useEffect(() => {
    const element = host.current;
    let active = true, renderer, controls, model, mixer, frame, resize;
    const scene = new THREE.Scene(), clock = new THREE.Clock();
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      const camera = new THREE.PerspectiveCamera(45, 1, .01, 100);
      camera.position.set(0, 1, 4);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      element.appendChild(renderer.domElement);
      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      scene.add(new THREE.HemisphereLight(0xffffff, 0x34574b, 3));
      const light = new THREE.DirectionalLight(0xffffff, 3); light.position.set(2,4,3); scene.add(light);
      resize = new ResizeObserver(() => { const w = Math.max(element.clientWidth,1), h = Math.max(element.clientHeight,1); camera.aspect = w/h; camera.updateProjectionMatrix(); renderer.setSize(w,h); });
      resize.observe(element);
      new GLTFLoader().load('/models/canine.glb', gltf => {
        if (!active) { disposeModel(gltf.scene); return; }
        model = gltf.scene;
        const bounds = new THREE.Box3().setFromObject(model), size = bounds.getSize(new THREE.Vector3()), center = bounds.getCenter(new THREE.Vector3());
        const group = new THREE.Group(); model.position.sub(center); group.add(model);
        group.scale.setScalar(2.3 / Math.max(size.x,size.y,size.z,.01)); scene.add(group);
        if (gltf.animations.length) { mixer = new THREE.AnimationMixer(model); mixer.clipAction(gltf.animations[0]).play(); }
        setMessage('');
      }, undefined, () => { if (active) setMessage('Awaiting Blender model'); });
      function render() { frame = requestAnimationFrame(render); controls.update(); mixer?.update(clock.getDelta()); renderer.render(scene,camera); }
      render();
    } catch { setMessage('3D rendering is unavailable in this browser'); }
    return () => { active = false; cancelAnimationFrame(frame); resize?.disconnect(); controls?.dispose(); mixer?.stopAllAction(); if (model) mixer?.uncacheRoot(model); disposeModel(model); renderer?.dispose(); renderer?.domElement.remove(); };
  }, []);
  return <><div className="model-canvas" ref={host} aria-label="Interactive virtual patient model" style={message ? { display: 'none' } : undefined}/>{message ? <div className="model-fallback"><Box size={42}/><strong>{message}</strong><small>Place canine.glb in frontend/public/models/</small></div> : <p className="notice">Drag to rotate · scroll to zoom · first exported animation plays automatically</p>}</>;
}
