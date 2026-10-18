import { useCallback, useEffect, useRef, useState } from 'react';

const errors = {
  NotAllowedError: 'Camera permission was denied. Allow camera access in your browser site settings.',
  NotFoundError: 'No camera was found. Connect your USB webcam and refresh the device list.',
  NotReadableError: 'The camera is unavailable. Close other apps using it and try again.',
  OverconstrainedError: 'The selected camera is unavailable. Refresh the list and select a connected camera.',
};

export function useCamera(videoRef) {
  const stream = useRef(null);
  const generation = useRef(0);
  const mounted = useRef(true);
  const [devices, setDevices] = useState([]);
  const [deviceId, setDeviceId] = useState('');
  const [status, setStatus] = useState('off');
  const [error, setError] = useState('');
  const [label, setLabel] = useState('No camera connected');

  const refreshDevices = useCallback(async () => {
    try {
      const list = await navigator.mediaDevices?.enumerateDevices();
      if (mounted.current) setDevices((list || []).filter(device => device.kind === 'videoinput'));
    } catch {
      if (mounted.current) setError('Could not refresh cameras. Check browser permissions.');
    }
  }, []);

  const release = useCallback(() => {
    stream.current?.getTracks().forEach(track => { track.onended = null; track.stop(); });
    stream.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, [videoRef]);

  const stop = useCallback(() => {
    generation.current += 1;
    release();
    if (mounted.current) { setStatus('off'); setLabel('Camera stopped'); }
  }, [release]);

  const start = useCallback(async () => {
    const request = ++generation.current;
    release();
    setError('');
    setStatus('starting');
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw Error('Camera access requires localhost or HTTPS and a supported browser.');
      const media = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { ...(deviceId ? { deviceId: { exact: deviceId } } : {}), width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } },
      });
      if (!mounted.current || request !== generation.current) { media.getTracks().forEach(track => track.stop()); return; }
      stream.current = media;
      const track = media.getVideoTracks()[0];
      track.onended = () => {
        stop();
        setError('Camera disconnected or access was revoked. Reconnect it and press Start Camera.');
      };
      videoRef.current.srcObject = media;
      await videoRef.current.play();
      if (!mounted.current || request !== generation.current) return;
      setStatus('on');
      setLabel(track.label || 'Active camera');
      await refreshDevices();
    } catch (cause) {
      if (mounted.current && request === generation.current) {
        release(); setStatus('off'); setLabel('Camera unavailable');
        setError(errors[cause.name] || cause.message);
      }
    }
  }, [deviceId, refreshDevices, release, stop, videoRef]);

  useEffect(() => {
    mounted.current = true;
    refreshDevices();
    navigator.mediaDevices?.addEventListener('devicechange', refreshDevices);
    return () => {
      mounted.current = false;
      generation.current += 1;
      release();
      navigator.mediaDevices?.removeEventListener('devicechange', refreshDevices);
    };
  }, [refreshDevices, release]);

  return { devices, deviceId, setDeviceId, status, label, error, setError, start, stop, refreshDevices };
}
