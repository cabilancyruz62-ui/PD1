import { useCallback, useEffect, useRef, useState } from 'react';

export function useAssessment() {
  const [state, setState] = useState(null), [connected, setConnected] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const retryConnection = useCallback(() => { setConnected(false); setConnectionAttempt(value => value + 1); }, []);
  const latest = useRef(null), inFlight = useRef(false), receivedAt = useRef(0);
  const acknowledgement = useRef({ key: null, time: 0 });
  const apply = useCallback(data => {
    if (latest.current && data.instance_id === latest.current.instance_id && data.revision < latest.current.revision) return;
    latest.current = data; receivedAt.current = Date.now(); setState(data); setConnected(true);
  }, []);

  useEffect(() => {
    let disposed = false, socket, reconnect, controller, polling = false;
    function connect() {
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws/assessment`);
      socket.onmessage = event => { if (!disposed) { try { const message = JSON.parse(event.data); if (message.type === 'assessment_state') apply(message.state); } catch {} } };
      socket.onerror = () => socket.close();
      socket.onclose = () => { if (!disposed) { setConnected(false); reconnect = setTimeout(connect, 2000); } };
    }
    async function fallback() {
      if (disposed || polling || socket?.readyState === WebSocket.OPEN) return;
      polling = true; controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 1500);
      try {
        const response = await fetch('/api/assessment/state', { signal: controller.signal });
        if (!response.ok) throw Error('Assessment backend unavailable');
        if (!disposed) apply(await response.json());
      } catch { if (!disposed) setConnected(false); }
      finally { clearTimeout(timeout); polling = false; }
    }
    connect(); fallback();
    const poll = setInterval(fallback, 2000);
    const watchdog = setInterval(() => { if (Date.now()-receivedAt.current > 3000) { setConnected(false); if (socket?.readyState === WebSocket.OPEN) socket.close(); } }, 500);
    return () => { disposed = true; clearTimeout(reconnect); clearInterval(poll); clearInterval(watchdog); controller?.abort(); socket?.close(); };
  }, [apply, connectionAttempt]);

  const command = useCallback(async (action, fields = {}) => {
    if (inFlight.current) return null;
    inFlight.current = true; setBusy(true); setError('');
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch('/api/assessment/command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, session_id: latest.current?.session_id || null, injection_stage_id: latest.current?.injection_stage_id || null, ...fields }), signal: controller.signal });
      const data = await response.json();
      if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'The command was rejected. Check the current assessment step.');
      apply(data); return data;
    } catch (cause) {
      setError(cause.name === 'AbortError' ? 'The backend did not respond. Check connection status before retrying.' : cause.message);
      return null;
    } finally { clearTimeout(timeout); inFlight.current = false; setBusy(false); }
  }, [apply]);

  // Start response timing only after a visible frame containing the scenario is rendered.
  useEffect(() => {
    if (state?.phase !== 'scenario_pending' || !connected || busy) return;
    let first, second;
    const key = `${state.session_id}:${state.scenario_id}`;
    const acknowledge = () => {
      if (document.hidden) return;
      acknowledgement.current = { key, time: Date.now() };
      first = requestAnimationFrame(() => { second = requestAnimationFrame(() => command('scenario_visible', { scenario_id: state.scenario_id })); });
    };
    const delay = acknowledgement.current.key === key ? Math.max(0, 1000-(Date.now()-acknowledgement.current.time)) : 0;
    const timer = setTimeout(acknowledge, delay);
    document.addEventListener('visibilitychange', acknowledge);
    return () => { clearTimeout(timer); cancelAnimationFrame(first); cancelAnimationFrame(second); document.removeEventListener('visibilitychange', acknowledge); };
  }, [state?.phase, state?.session_id, state?.scenario_id, busy, connected, command]);

  // A retained snapshot is useful during reconnects, but its live angle must
  // stop being assessable as soon as the backend connection is lost.
  const displayState = !connected && state?.angle ? { ...state, angle: { ...state.angle, fresh: false } } : state;
  return { state: displayState, connected, busy, error, setError, command, retryConnection, receivedAt: receivedAt.current };
}
