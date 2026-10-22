import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { createDogModel } from '../lib/dogModel.js';
import { defaultPlacement } from '../lib/dogPlacement.js';
import { getBreedProfile } from '../data/breeds.js';

export { defaultPlacement } from '../lib/dogPlacement.js';

export function DummyOverlayControls({ placement, setPlacement, preview, setPreview, pose, breedId }) {
  const breed = getBreedProfile(breedId);
  const fields = [['x', 'Horizontal position', 0, 100, '%'], ['y', 'Vertical position', 0, 100, '%'], ['size', 'Size', 15, 100, '%'], ['rotation', 'Screen rotation', -180, 180, '°'], ['yaw', 'Turn left / right', -180, 180, '°'], ['pitch', 'Tilt forward / back', -45, 45, '°'], ['opacity', 'Opacity', 10, 100, '%']];
  return <><h3 className="settings-subtitle">{breed.label} alignment</h3><p className="notice">Align the dog with the dummy. Each breed keeps its own placement for this page session.</p><label className="toggle-row"><span>Preview for alignment</span><input type="checkbox" checked={preview} onChange={e => setPreview(e.target.checked)}/><span className="switch" aria-hidden="true"/></label><p className="notice" role="status">{pose ? `Dog pose: ${pose === 'lying' ? 'lying down' : 'standing'}` : preview ? 'Alignment preview: standing' : 'Hidden until assessment starts'}</p>{fields.map(([key, label, min, max, unit]) => <label className="field" key={key}>{label}: {placement[key]}{unit}<input type="range" min={min} max={max} value={placement[key]} onChange={e => setPlacement(current => ({ ...current, [key]: Number(e.target.value) }))}/></label>)}<button className="secondary" onClick={() => setPlacement({ ...defaultPlacement })}>Reset this breed's placement</button><p className="notice">Keep the camera and dummy fixed. Realign after moving or mirroring the camera.</p></>;
}

export default function DummyOverlay({ placement, pose, breedId }) {
  const breed = getBreedProfile(breedId);
  const host = useRef(null), motion = useRef({ pose, placement });
  const [error, setError] = useState('');
  motion.current = { pose, placement };
  useEffect(() => {
    const element = host.current;
    const scene = new THREE.Scene(), orientation = new THREE.Group();
    let renderer, frame, observer, dog;
    setError('');
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      element.appendChild(renderer.domElement);
      const camera = new THREE.OrthographicCamera(-3.8, 3.8, 2.4, -2.4, .1, 30);
      camera.position.set(0, 1.4, 8); camera.lookAt(0, 0, 0);
      scene.add(new THREE.HemisphereLight(0xfff5e5, 0x344b46, 2));
      const light = new THREE.DirectionalLight(0xfff3df, 3.2); light.position.set(-3, 5, 6); scene.add(light);
      const rim = new THREE.DirectionalLight(0xdcefff, 1.8); rim.position.set(3, 3, -4); scene.add(rim);
      dog = createDogModel(breed);
      const centered = new THREE.Group(); centered.position.y = -1.2; centered.add(dog.group);
      orientation.add(centered); scene.add(orientation);
      observer = new ResizeObserver(() => {
        const width = Math.max(element.clientWidth, 1), height = Math.max(element.clientHeight, 1);
        const halfHeight = Math.max(2.4, 3.8 * height / width);
        camera.left = -halfHeight * width / height; camera.right = halfHeight * width / height;
        camera.top = halfHeight; camera.bottom = -halfHeight; camera.updateProjectionMatrix();
        renderer.setSize(width, height);
      });
      observer.observe(element);
      let blend = motion.current.pose === 'lying' ? 1 : 0, previous = performance.now();
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
      function render(now) {
        frame = requestAnimationFrame(render);
        const target = motion.current.pose === 'lying' ? 1 : 0;
        const delta = Math.max(0, (now - previous) / 1000); previous = now;
        blend = reducedMotion.matches ? target : THREE.MathUtils.lerp(blend, target, 1 - Math.exp(-3 * delta));
        dog.setPose(blend);
        orientation.rotation.set(THREE.MathUtils.degToRad(motion.current.placement.pitch || 0), THREE.MathUtils.degToRad(motion.current.placement.yaw || 0), 0);
        renderer.render(scene, camera);
      }
      frame = requestAnimationFrame(render);
    } catch { setError('The 3D dog needs WebGL. Try a browser with hardware acceleration enabled.'); }
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); dog?.dispose(); renderer?.dispose(); renderer?.domElement.remove(); };
  }, [breed]);
  return <div className="dummy-overlay" role="img" aria-label={`${breed.label} model: ${pose === 'lying' ? 'lying down' : 'standing'}`} style={{ left: `${placement.x}%`, top: `${placement.y}%`, width: `${placement.size}vw`, opacity: placement.opacity / 100, transform: `translate(-50%, -50%) rotate(${placement.rotation}deg)` }}><div ref={host} className="dummy-overlay-canvas"/>{error && <p role="alert">{error}</p>}</div>;
}
