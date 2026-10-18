import { useEffect, useRef, useState } from 'react';

const edges = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];

export default function HandOverlay({ videoRef, enabled, mirrored, onStatus }) {
  const canvas = useRef(null);
  const [failure, setFailure] = useState('');
  useEffect(() => {
    let cancelled = false, worker, frame, pending = false, lastTime = -1, lastInference = 0;
    const ctx = canvas.current.getContext('2d');
    ctx.clearRect(0, 0, canvas.current.width, canvas.current.height);
    setFailure('');
    if (!enabled) { onStatus('Off'); return; }
    onStatus('Loading tracker');
    worker = new Worker(new URL('../workers/hands.js', import.meta.url), { type: 'module' });
    const fail = message => { if (!cancelled) { cancelled = true; ctx.clearRect(0, 0, canvas.current.width, canvas.current.height); setFailure(message); onStatus('Tracker unavailable'); worker.terminate(); cancelAnimationFrame(frame); } };
    worker.onerror = () => fail('Hand tracker could not start. Check your network and browser support.');
    worker.onmessage = ({ data }) => {
      if (cancelled) return;
      if (data.error) { fail(data.error); return; }
      if (data.ready) { onStatus('Searching for hands'); frame = requestAnimationFrame(loop); return; }
      pending = false;
      const c = canvas.current;
      c.width = data.width; c.height = data.height;
      ctx.clearRect(0, 0, c.width, c.height);
      onStatus(data.landmarks.length ? `${data.landmarks.length} hand${data.landmarks.length > 1 ? 's' : ''} detected` : 'Searching for hands');
      ctx.strokeStyle = '#67f5cc'; ctx.fillStyle = '#eafffa'; ctx.lineWidth = Math.max(2, c.width / 450);
      for (const hand of data.landmarks) {
        for (const [a,b] of edges) { ctx.beginPath(); ctx.moveTo(hand[a].x*c.width, hand[a].y*c.height); ctx.lineTo(hand[b].x*c.width, hand[b].y*c.height); ctx.stroke(); }
        for (const p of hand) { ctx.beginPath(); ctx.arc(p.x*c.width,p.y*c.height,Math.max(2,c.width/300),0,Math.PI*2); ctx.fill(); }
      }
    };
    async function loop(now) {
      if (cancelled) return;
      const v = videoRef.current;
      if (!pending && v?.readyState >= 2 && v.currentTime !== lastTime && now-lastInference >= 66) {
        pending = true; lastTime = v.currentTime; lastInference = now;
        try {
          const bitmap = await createImageBitmap(v);
          if (cancelled) bitmap.close();
          else worker.postMessage({ bitmap, timestamp: now }, [bitmap]);
        } catch { fail('Cannot read camera frames for hand tracking. Restart the camera and tracker.'); return; }
      }
      if (!cancelled) frame = requestAnimationFrame(loop);
    }
    worker.postMessage({ initialize: true });
    return () => { cancelled = true; cancelAnimationFrame(frame); worker.terminate(); };
  }, [enabled, videoRef, onStatus]);
  return <><canvas ref={canvas} className={`hand-overlay ${mirrored ? 'mirrored' : ''}`} aria-hidden="true" />{failure && <div className="tracker-error" role="status">{failure}</div>}</>;
}
