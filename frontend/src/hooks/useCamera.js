import { useCallback, useEffect, useRef, useState } from 'react';
import { createCameraRegistry, cameraOptionLabel } from '../lib/cameras';

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
  const registry = useRef(null);
  if (!registry.current) registry.current = createCameraRegistry();
  const scan = useRef(0);
  const [devices, setDevices] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [activeDeviceId, setActiveDeviceId] = useState('');
  const [deviceId, setDeviceId] = useState('');
  const [status, setStatus] = useState('off');
  const [error, setError] = useState('');
  const [label, setLabel] = useState('No camera connected');

  const refreshDevices = useCallback(async () => {
    const request = ++scan.current;
    if (mounted.current) setRefreshing(true);
    try {
      const list = await navigator.mediaDevices?.enumerateDevices();
      if (mounted.current && request === scan.current) setDevices(registry.current.list(list));
    } catch {
      if (mounted.current && request === scan.current) setError('Could not refresh cameras. Check browser permissions.');
    } finally {
      if (mounted.current && request === scan.current) setRefreshing(false);
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
    if (mounted.current) { setStatus('off'); setLabel('Camera stopped'); setActiveDeviceId(''); }
  }, [release]);

  const start = useCallback(async () => {
    const request = ++generation.current;
    release();
    setActiveDeviceId('');
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
      const actualId = track.getSettings?.().deviceId || deviceId;
      setActiveDeviceId(actualId);
      const appId = registry.current.identify(actualId);
      setLabel(appId ? cameraOptionLabel({ appId, label: track.label || 'Active camera' }) : track.label || 'Active camera');
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
      scan.current += 1;
      release();
      navigator.mediaDevices?.removeEventListener('devicechange', refreshDevices);
    };
  }, [refreshDevices, release]);

  return { devices, deviceId, setDeviceId, activeDeviceId, refreshing, status, label, error, setError, start, stop, refreshDevices };
}
