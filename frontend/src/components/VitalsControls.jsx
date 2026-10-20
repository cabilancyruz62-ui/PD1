export default function VitalsControls({ enabled, setEnabled, source, setSource, connected, setConnected, message }) {
  return <div className="vitals-controls">
    <label className="toggle-row"><span>Require wire connection for vitals</span><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)}/><span className="switch" aria-hidden="true"/></label>
    {enabled && <><label className="field">Wire signal source<select value={source} onChange={e => setSource(e.target.value)}><option value="simulation">Simulated wire (no ESP32 needed)</option><option value="esp32">ESP32 hardware</option></select></label>
    {source === 'simulation' && <label className="toggle-row"><span>Simulate wire connected</span><input type="checkbox" checked={connected} onChange={e => setConnected(e.target.checked)}/><span className="switch" aria-hidden="true"/></label>}</>}
    <p className="notice" role="status">{message}</p>
    <p className="notice">Wire connection controls monitor visibility. Vitals are simulated.</p>
  </div>;
}
