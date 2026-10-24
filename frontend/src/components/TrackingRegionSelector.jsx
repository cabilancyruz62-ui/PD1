import { useEffect, useRef, useState } from 'react';
import { captureTrackingFrame } from '../lib/tracking.js';

export default function TrackingRegionSelector({ frame, videoRef, mode, mirrored, onConfirm, onCancel }) {
  const canvas = useRef(null), origin = useRef(null), cancel = useRef(null), latestBox = useRef(null), mounted = useRef(true);
  const [box, setBox] = useState(null);
  const [submitting, setSubmitting] = useState(false), [error, setError] = useState('');
  latestBox.current = box;
  useEffect(() => {
    mounted.current = true;
    let animation;
    function draw() {
      animation = requestAnimationFrame(draw);
      const video = videoRef.current, context = canvas.current?.getContext('2d');
      if (!context || !video || video.readyState < 2) return;
      context.drawImage(video, 0, 0, frame.width, frame.height);
      if (latestBox.current) {
        context.fillStyle = '#85f5cf33'; context.fillRect(...latestBox.current);
        context.strokeStyle = '#85f5cf'; context.lineWidth = 2; context.strokeRect(...latestBox.current);
      }
    }
    draw();
    cancel.current?.focus();
    return () => { mounted.current = false; cancelAnimationFrame(animation); };
  }, [frame, videoRef]);
  useEffect(() => {
    const escape = event => { if (event.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', escape);
    return () => window.removeEventListener('keydown', escape);
  }, [onCancel]);
  function point(event) {
    const rect = canvas.current.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    return [Math.max(0, Math.min(frame.width, (mirrored ? 1 - x : x) * frame.width)),
      Math.max(0, Math.min(frame.height, (event.clientY - rect.top) / rect.height * frame.height))];
  }
  function move(event) {
    if (!origin.current) return;
    const [x, y] = point(event), [startX, startY] = origin.current;
    setBox([Math.min(x, startX), Math.min(y, startY), Math.abs(x - startX), Math.abs(y - startY)]);
  }
  const minimum = mode === 'orb' ? 48 : 12;
  const valid = box && box[2] >= minimum && box[3] >= minimum;
  async function confirm() {
    if (!valid || submitting) return;
    setSubmitting(true); setError('');
    try {
      // Read the real video, never the selection canvas containing its outline.
      const fresh = await captureTrackingFrame(videoRef.current);
      if (!mounted.current) return;
      if (!fresh) throw Error('The camera is not ready. Try selecting again.');
      if (fresh.width !== frame.width || fresh.height !== frame.height) throw Error('Camera dimensions changed. Cancel and select the pad again.');
      onConfirm({ ...fresh, roi: [box[0] / frame.width, box[1] / frame.height, box[2] / frame.width, box[3] / frame.height] });
    } catch (cause) { if (mounted.current) setError(cause.message); }
    finally { if (mounted.current) setSubmitting(false); }
  }
  return <section className="tracking-selection-screen" role="dialog" aria-modal="true" aria-labelledby="tracking-region-title">
    <div className="tracking-selection-card">
      <h2 id="tracking-region-title">Select the original pad surface</h2>
      <p>Live camera: keep the camera and pad still, then drag around existing pad details. Exclude hands, background, sensors and printed helpers.</p>
      <canvas ref={canvas} width={frame.width} height={frame.height} className={mirrored ? 'mirrored' : ''} aria-label="Drag to select pad region"
        onPointerDown={event => { origin.current = point(event); setBox(null); event.currentTarget.setPointerCapture(event.pointerId); }}
        onPointerMove={move} onPointerUp={event => { move(event); origin.current = null; event.currentTarget.releasePointerCapture(event.pointerId); }}
        onPointerCancel={() => { origin.current = null; }}/>
      <p role="status">{box ? `Selected ${Math.round(box[2])} × ${Math.round(box[3])} pixels.` : 'No region selected.'}{!valid && ` Choose at least ${minimum} pixels per side.`}</p>
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="action-row"><button className="secondary" ref={cancel} onClick={onCancel}>Cancel</button>
        <button className="primary" disabled={!valid || submitting} onClick={confirm}>{submitting ? 'Starting tracking…' : 'Use pad region'}</button></div>
    </div>
  </section>;
}
