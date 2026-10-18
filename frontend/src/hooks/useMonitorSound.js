import { useEffect, useRef, useState } from 'react';

export function useMonitorSound(active, heartRate) {
  const context = useRef(null), nodes = useRef(new Set());
  const [enabled, setEnabled] = useState(false), [error, setError] = useState('');
  const latest = useRef({ active, heartRate, enabled });
  latest.current = { active, heartRate, enabled };

  async function toggle() {
    if (enabled) {
      latest.current.enabled = false;
      nodes.current.forEach(node => { try { node.stop(); } catch {} });
      setEnabled(false); return;
    }
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) throw Error('Audio is unavailable in this browser.');
      context.current ||= new Audio();
      await context.current.resume();
      if (context.current.state !== 'running') throw Error('Browser audio is paused. Try enabling sound again.');
      setError(''); setEnabled(true);
    } catch (cause) { setError(cause.message); setEnabled(false); }
  }

  useEffect(() => {
    let nextBeat = 0;
    const timer = setInterval(() => {
      const audio = context.current, settings = latest.current;
      if (!audio || !settings.enabled || !settings.active || settings.heartRate <= 0 || document.hidden || audio.state !== 'running') { nextBeat = 0; return; }
      const time = audio.currentTime;
      if (time < nextBeat) return;
      nextBeat = time + 60/Math.max(1,settings.heartRate);
      const oscillator = audio.createOscillator(), gain = audio.createGain();
      oscillator.frequency.value = 900;
      gain.gain.setValueAtTime(0,time);
      gain.gain.linearRampToValueAtTime(.025,time+.008);
      gain.gain.exponentialRampToValueAtTime(.0001,time+.075);
      oscillator.connect(gain); gain.connect(audio.destination);
      nodes.current.add(oscillator);
      oscillator.onended = () => { nodes.current.delete(oscillator); oscillator.disconnect(); gain.disconnect(); };
      oscillator.start(time); oscillator.stop(time+.08);
    }, 25);
    return () => { clearInterval(timer); nodes.current.forEach(node => { try { node.stop(); } catch {} }); context.current?.close().catch(() => {}); };
  }, []);
  return { enabled, toggle, error };
}
