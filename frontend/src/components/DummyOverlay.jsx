import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

export const defaultPlacement = { x: 65, y: 57, size: 45, rotation: 0, opacity: 80 };

export function DummyOverlayControls({ placement, setPlacement, preview, setPreview, pose }) {
  const fields = [['x', 'Horizontal position', 0, 100, '%'], ['y', 'Vertical position', 0, 100, '%'], ['size', 'Size', 15, 100, '%'], ['rotation', 'Rotation', -180, 180, '°'], ['opacity', 'Opacity', 10, 100, '%']];
  return <><h3 className="settings-subtitle">Dummy overlay placement</h3><p className="notice">Keep the camera and dummy fixed. Align this placeholder over the dummy; placement is manual. Option 1 starts standing, lies down after initial injection completion, and stands after correct intervention completion. Option 2 starts lying down. End Assessment hides the dog.</p><label className="toggle-row"><span>Preview for alignment</span><input type="checkbox" checked={preview} onChange={e => setPreview(e.target.checked)}/><span className="switch" aria-hidden="true"/></label><p className="notice" role="status">{pose ? `Dog pose: ${pose === 'lying' ? 'lying down' : 'standing'}` : preview ? 'Alignment preview: standing' : 'Hidden until an assessment starts'}</p>{fields.map(([key, label, min, max, unit]) => <label className="field" key={key}>{label}: {placement[key]}{unit}<input type="range" min={min} max={max} value={placement[key]} onChange={e => setPlacement(current => ({ ...current, [key]: Number(e.target.value) }))}/></label>)}<button className="secondary" onClick={() => setPlacement({ ...defaultPlacement })}>Reset placement</button><p className="notice">Simple animated placeholder, not a clinical representation. Camera mirroring or moving the camera requires realignment.</p></>;
}

export default function DummyOverlay({ placement, pose }) {
  const host = useRef(null), motion = useRef({ pose });
  const [error, setError] = useState('');
  motion.current = { pose };
  useEffect(() => {
    const element = host.current;
    const scene = new THREE.Scene(), dog = new THREE.Group();
    let renderer, frame, observer;
    const geometries = [], materials = [];
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      element.appendChild(renderer.domElement);
      const camera = new THREE.OrthographicCamera(-3.4, 3.4, 2, -2, .1, 30);
      camera.position.set(0, 2.8, 7); camera.lookAt(0, 0, 0);
      scene.add(new THREE.HemisphereLight(0xffffff, 0x344b46, 2.5));
      const light = new THREE.DirectionalLight(0xffffff, 3); light.position.set(-2, 4, 5); scene.add(light);
      function part(position, scale, color, parent = dog) {
        const geometry = new THREE.SphereGeometry(1, 24, 16);
        const material = new THREE.MeshStandardMaterial({ color, roughness: .85 });
        geometries.push(geometry); materials.push(material);
        const mesh = new THREE.Mesh(geometry, material); mesh.position.set(...position); mesh.scale.set(...scale); parent.add(mesh);
        return mesh;
      }
      const coat = 0xc69b6d, dark = 0x74513c;
      part([0, 0, 0], [1.5, .58, .58], coat);
      part([-1.5, .25, 0], [.62, .55, .48], coat);
      part([-2.02, .1, .16], [.48, .24, .32], 0xe2c29c);
      part([-2.4, .14, .18], [.13, .14, .22], 0x293b39);
      part([-1.23, .2, .43], [.23, .48, .13], dark).rotation.z = -.25;
      part([-1.71, .46, .4], [.065, .065, .035], 0x172625);
      // Four legs pivot at the hips/shoulders as the torso lowers.
      const legs = [];
      for (const x of [-.9, .95]) for (const z of [-.35, .38]) {
        const leg = new THREE.Group(); leg.position.set(x, -.2, z); dog.add(leg); legs.push(leg);
        part([0, -.32, 0], [.18, .38, .18], coat, leg);
        part([0, -.82, 0], [.12, .3, .13], coat, leg);
        part([-.12, -1.08, .05], [.28, .12, .2], 0xe2c29c, leg);
      }
      part([1.65, -.05, -.03], [.7, .14, .15], dark).rotation.z = .3;
      scene.add(dog);
      observer = new ResizeObserver(() => {
        const width = Math.max(element.clientWidth, 1), height = Math.max(element.clientHeight, 1);
        camera.left = -2 * width / height; camera.right = 2 * width / height; camera.updateProjectionMatrix();
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
        dog.position.y = THREE.MathUtils.lerp(.5, -.4, blend);
        for (const leg of legs) leg.rotation.z = -1.35 * blend;
        renderer.render(scene, camera);
      }
      frame = requestAnimationFrame(render);
    } catch { setError('The dummy placeholder needs WebGL. Try a browser with hardware acceleration enabled.'); }
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose()); renderer?.dispose(); renderer?.domElement.remove(); };
  }, []);
  return <div className="dummy-overlay" role="img" aria-label={`Virtual dog placeholder: ${pose === 'lying' ? 'lying down' : 'standing'}`} style={{ left: `${placement.x}%`, top: `${placement.y}%`, width: `${placement.size}vw`, opacity: placement.opacity / 100, transform: `translate(-50%, -50%) rotate(${placement.rotation}deg)` }}><div ref={host} className="dummy-overlay-canvas"/>{error && <p role="alert">{error}</p>}</div>;
}
