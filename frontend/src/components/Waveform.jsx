import { useEffect, useRef } from 'react';
import { waveSample, waveSpec } from '../lib/simulation';

export default function Waveform({ channel, values, active }) {
  const canvas = useRef(null), latest = useRef({ values, active });
  latest.current = { values, active };
  useEffect(() => {
    const element = canvas.current, ctx = element.getContext('2d');
    let frame, last = 0, phase = 0, accumulated = 0, wasActive = false;
    const history = new Array(480).fill(null);
    let width = 240, height = 58;
    const resize = new ResizeObserver(() => {
      width = Math.max(1, element.clientWidth); height = Math.max(1, element.clientHeight);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      element.width = width*dpr; element.height = height*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
    });
    resize.observe(element);
    function draw(now) {
      const dt = last ? Math.min((now-last)/1000,.1) : 0; last = now;
      const { active: running, values: current } = latest.current;
      ctx.clearRect(0,0,width,height);
      ctx.strokeStyle = '#d8fff10c'; ctx.lineWidth = .5;
      for (let x=0;x<width;x+=18) { ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,height); ctx.stroke(); }
      for (let y=0;y<height;y+=14) { ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(width,y); ctx.stroke(); }
      if (!running) { if (wasActive) history.fill(null); wasActive = false; phase = 0; accumulated = 0; }
      else {
        wasActive = true;
        const spec = waveSpec(channel, current);
        phase += spec.rate/60*dt; accumulated += dt;
        if (accumulated >= 1/60) {
          accumulated %= 1/60; history.push(spec.rate === 0 ? 0 : waveSample(channel,phase)*spec.amplitude); history.shift();
        }
        ctx.strokeStyle = getComputedStyle(element).color; ctx.lineWidth = 1.6;
        ctx.shadowColor = ctx.strokeStyle; ctx.shadowBlur = 3;
        ctx.beginPath(); let started = false;
        history.forEach((sample,i) => {
          if (sample === null) return;
          const x=i/(history.length-1)*width, y=height*.5-sample*height*.24;
          if (!started) { ctx.moveTo(x,y); started=true; } else ctx.lineTo(x,y);
        });
        ctx.stroke(); ctx.shadowBlur = 0;
      }
      frame = requestAnimationFrame(draw);
    }
    frame = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(frame); resize.disconnect(); };
  }, [channel]);
  return <canvas ref={canvas} className="monitor-wave" role="img" aria-label={`${channel} illustrative ${active ? 'animated waveform' : 'monitor paused'}`}/>;
}
