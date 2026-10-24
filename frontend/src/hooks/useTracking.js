import { useEffect, useState } from 'react';
import { captureTrackingFrame, hasFreshTarget } from '../lib/tracking.js';

export function useTracking({ videoRef, mode, enabled, cameraKey }) {
  const [selection, setSelection] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({ status: 'idle', detail: '', result: null });
  const [now, setNow] = useState(0);
  const selected = selection?.mode === mode && selection.cameraKey === cameraKey ? selection : null;
  useEffect(() => {
    setSelection(current => current && (current.cameraKey !== cameraKey || current.mode !== mode
      || (!enabled && mode === 'optical-flow')) ? null : current);
  }, [mode, cameraKey, enabled]);
  useEffect(() => {
    if (!enabled || mode === 'normal') {
      setState({ status: 'idle', detail: '', result: null });
      return;
    }
    let disposed = false, socket, reconnect, inFlight = false, sentAt = 0;
    let ready = false, maySend = false, initialSent = false;
    let lastActivity = performance.now(), terminalError = '';
    setState({ status: 'connecting', detail: 'Connecting tracking…', result: null });
    function connect() {
      ready = false; maySend = false; inFlight = false; initialSent = false;
      lastActivity = performance.now();
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws/tracking`);
      socket.onopen = () => socket.send(JSON.stringify({ type: 'configure', design: mode, marker_id: 0,
        ...(selected ? { roi: selected.roi } : {}),
      }));
      socket.onmessage = event => {
        if (disposed) return;
        lastActivity = performance.now();
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'error') {
            terminalError = message.message;
            setState({ status: 'error', detail: message.message, result: null });
            return;
          }
          if (message.design !== mode) return;
          if (message.type === 'ready') {
            ready = true; maySend = mode === 'aruco' || Boolean(selected);
            setState({ status: message.status, detail: message.detail, result: null });
          } else if (message.type === 'tracking_result') {
            inFlight = false;
            maySend = message.status !== 'needs_selection';
            const result = { ...message, cameraKey, capturedAt: sentAt };
            setState({ status: message.status, detail: message.detail, result });
            setNow(performance.now());
          }
        } catch {
          terminalError = 'Tracking returned an unreadable response. Retry tracking.';
          setState({ status: 'error', detail: terminalError, result: null });
          socket.close();
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        ready = false;
        if (disposed) return;
        if (!terminalError) setState({ status: 'disconnected', detail: 'Tracking disconnected. Reconnecting…', result: null });
        // LK requires a new manual selection after its stream is interrupted.
        if (mode === 'optical-flow' && selected) { setSelection(null); return; }
        if (!terminalError) reconnect = setTimeout(connect, 2000);
      };
    }
    async function pump() {
      if (disposed) return;
      const tick = performance.now();
      setNow(tick);
      if (!terminalError && tick - lastActivity > 5000 && (!ready || inFlight)) {
        socket?.close(); return;
      }
      if (!ready || !maySend || inFlight || socket?.readyState !== WebSocket.OPEN || document.hidden) return;
      inFlight = true;
      const frameSocket = socket;
      try {
        const frame = !initialSent && selected ? selected : await captureTrackingFrame(videoRef.current);
        if (disposed || socket !== frameSocket || frameSocket.readyState !== WebSocket.OPEN) return;
        if (!frame) { inFlight = false; return; }
        sentAt = frame.capturedAt;
        initialSent = true;
        socket.send(frame.blob);
      } catch (error) {
        terminalError = error.message;
        setState({ status: 'error', detail: error.message, result: null });
        socket?.close();
      }
    }
    connect();
    const timer = setInterval(pump, 100);
    return () => {
      disposed = true; clearInterval(timer); clearTimeout(reconnect); socket?.close();
    };
  }, [videoRef, mode, enabled, cameraKey, selected, attempt]);

  const fresh = enabled && mode !== 'normal' && hasFreshTarget(state.result, mode, cameraKey, now);
  const status = !enabled ? 'idle' : state.status === 'tracking' && !fresh ? 'searching' : state.status;
  const diagnostics = state.result?.design === mode && state.result.cameraKey === cameraKey ? state.result.metrics : null;
  return { ...state, status, fresh, result: fresh ? state.result : null, diagnostics,
    selectRegion: frame => setSelection({ ...frame, mode, cameraKey }),
    clearSelection: () => setSelection(null),
    retry: () => { if (mode === 'optical-flow') setSelection(null); setAttempt(value => value + 1); },
  };
}
