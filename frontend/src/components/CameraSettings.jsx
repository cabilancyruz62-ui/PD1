import { Camera, RefreshCw } from 'lucide-react';
import { cameraOptionLabel } from '../lib/cameras';

export default function CameraSettings({ camera }) {
  const busy = camera.status === 'starting';
  const selectedMissing = camera.deviceId && !camera.devices.some(device => device.deviceId === camera.deviceId);
  return <div className="camera-settings">
    <h3 className="settings-subtitle">Camera selection</h3>
    <p className="notice">Select a camera. It connects automatically.</p>
    <label className="field">Camera<select value={camera.deviceId} onChange={e => camera.setDeviceId(e.target.value)} disabled={busy}>
      <option value="">System default camera</option>
      {selectedMissing && <option value={camera.deviceId}>Selected camera unavailable — choose another</option>}
      {camera.devices.map((device,index) => <option key={device.deviceId || `hidden-${index}`} value={device.deviceId || `hidden-${index}`} disabled={!device.selectable}>{cameraOptionLabel(device)}</option>)}
    </select></label>
    <button className="text-button" onClick={camera.refreshDevices} disabled={camera.refreshing}><RefreshCw size={13}/>{camera.refreshing ? 'Detecting cameras…' : 'Refresh camera list'}</button>
    <ul className="camera-device-list" aria-label="Detected cameras">{camera.devices.map((device,index) => <li key={device.deviceId || `hidden-${index}`} className={camera.status === 'on' && device.deviceId === camera.activeDeviceId ? 'camera-active' : ''}>
      <code>{device.appId || '—'}</code><span>{device.label || 'Camera name hidden'}<small>{!device.selectable ? 'Allow camera access to identify this device' : camera.status === 'on' && device.deviceId === camera.activeDeviceId ? 'Active camera' : camera.deviceId === device.deviceId ? 'Selected' : 'Available'}</small></span>
    </li>)}</ul>
    {!camera.devices.length && <p className="notice" role="status">No camera found. Connect one and retry.</p>}
    {camera.devices.some(device => !device.label || !device.selectable) && <p className="notice">Allow camera access to see device names.</p>}
    {camera.status !== 'on' && <div className="action-row"><button className="primary" disabled={busy || Boolean(selectedMissing)} onClick={camera.start}><Camera size={16}/>{busy ? 'Connecting...' : 'Retry camera'}</button></div>}
    {selectedMissing && <p className="notice" role="status">Camera disconnected. Reconnect it or select another.</p>}

  </div>;
}
