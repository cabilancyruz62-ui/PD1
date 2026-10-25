import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { getCanineModelPath, centerAndScaleCanine, disposeCanineScene, getCanineClip, describeCanineLoadError } from '../lib/canineAsset.js';
import { defaultPlacement } from '../lib/dogPlacement.js';

export { defaultPlacement } from '../lib/dogPlacement.js';

export function DummyOverlayControls({ placement, setPlacement, preview, setPreview, pose, tracked = false }) {
  const fields = [['x', 'Horizontal position', 0, 100, '%'], ['y', 'Vertical position', 0, 100, '%'], ['size', 'Size', 15, 100, '%'], ['rotation', 'Screen rotation', -180, 180, '°'], ['yaw', 'Turn left / right', -180, 180, '°'], ['pitch', 'Tilt forward / back', -45, 45, '°'], ['opacity', 'Opacity', 10, 100, '%']];
  return <><h3 className="settings-subtitle">Assigned breed GLB alignment</h3>
    <p className="notice">{tracked ? 'Target tracking controls screen placement. Adjust the GLB viewing angle and opacity here.' : 'Align the assigned breed beside the physical forelimb dummy. Each patient breed retains independent placement settings.'}</p>
    {!tracked && <label className="toggle-row"><span>Preview for alignment</span><input type="checkbox" checked={preview} onChange={e => setPreview(e.target.checked)}/><span className="switch" aria-hidden="true"/></label>}
    <p className="notice" role="status">{pose ? `Requested animation: ${pose === 'lying' ? 'lying' : 'standing'}` : tracked ? 'Standing preview while the target is tracked' : preview ? 'Alignment preview: standing' : 'Hidden until assessment starts'}</p>
    {fields.filter(([key]) => !tracked || ['yaw', 'pitch', 'opacity'].includes(key)).map(([key, label, min, max, unit]) => <label className="field" key={key}>{label}: {placement[key]}{unit}<input type="range" min={min} max={max} value={placement[key]} onChange={e => setPlacement(current => ({ ...current, [key]: Number(e.target.value) }))}/></label>)}
    <button className="secondary" onClick={() => setPlacement({ ...defaultPlacement })}>Reset placement</button>
    <p className="notice">Standing/lying animations play only when included in the assigned GLB. There is no generated fallback dog.</p>
  </>;
}

export default function DummyOverlay({ breedId, placement, pose, visible = true }) {
  const modelPath = getCanineModelPath(breedId);
  const host = useRef(null), motion = useRef({ pose, placement, visible });
  const [error, setError] = useState('');
  motion.current = { pose, placement, visible };
  useEffect(() => {
    const element = host.current;
    const scene = new THREE.Scene(), orientation = new THREE.Group();
    let active = true, renderer, frame, observer, imported, mixer, animations = [], previousPose, activeClip;
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
      scene.add(orientation);
      new GLTFLoader().load(modelPath, gltf => {
        if (!active) { disposeCanineScene(gltf.scene); return; }
        try {
          const { wrapper } = centerAndScaleCanine(gltf.scene);
          imported = gltf.scene; orientation.add(wrapper);
          animations = gltf.animations;
          if (animations.length) mixer = new THREE.AnimationMixer(imported);
        } catch (exception) {
          disposeCanineScene(gltf.scene);
          setError(describeCanineLoadError(exception, modelPath));
        }
      }, undefined, exception => { if (active) setError(describeCanineLoadError(exception, modelPath)); });
      observer = new ResizeObserver(() => {
        const width = Math.max(element.clientWidth, 1), height = Math.max(element.clientHeight, 1);
        const halfHeight = Math.max(2.4, 3.8 * height / width);
        camera.left = -halfHeight * width / height; camera.right = halfHeight * width / height;
        camera.top = halfHeight; camera.bottom = -halfHeight; camera.updateProjectionMatrix();
        renderer.setSize(width, height);
      });
      observer.observe(element);
      let previous = performance.now();
      function render(now) {
        frame = requestAnimationFrame(render);
        const delta = Math.min(.1, Math.max(0, (now - previous) / 1000)); previous = now;
        if (!motion.current.visible) return;
        const pose = motion.current.pose === 'lying' ? 'lying' : 'standing';
        if (mixer && pose !== previousPose) {
          const clip = getCanineClip(animations, pose);
          if (clip !== activeClip) {
            mixer.stopAllAction();
            if (clip) mixer.clipAction(clip).reset().play();
            activeClip = clip;
          }
          previousPose = pose;
        }
        mixer?.update(delta);
        orientation.rotation.set(THREE.MathUtils.degToRad(motion.current.placement.pitch || 0), THREE.MathUtils.degToRad(motion.current.placement.yaw || 0), 0);
        renderer.render(scene, camera);
      }
      frame = requestAnimationFrame(render);
    } catch { setError('The 3D canine needs WebGL. Enable hardware acceleration.'); }
    return () => {
      active = false; cancelAnimationFrame(frame); observer?.disconnect();
      mixer?.stopAllAction(); if (imported) mixer?.uncacheRoot(imported);
      disposeCanineScene(imported); renderer?.dispose(); renderer?.forceContextLoss(); renderer?.domElement.remove();
    };
  }, [modelPath]);
  return <div className="dummy-overlay" role="img" aria-label={`Patient breed GLB: ${pose === 'lying' ? 'lying requested' : 'standing requested'}`} style={{ left: `${placement.x}%`, top: `${placement.y}%`, width: `${placement.size}vw`, opacity: placement.opacity / 100, transform: `translate(-50%, -50%) rotate(${placement.rotation}deg)` }}><div ref={host} className="dummy-overlay-canvas"/>{error && <p role="alert">{error}</p>}</div>;
}
