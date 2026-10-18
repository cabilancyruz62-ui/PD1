import { Camera, RefreshCw } from 'lucide-react';
import { cameraOptionLabel } from '../lib/cameras';

export default function CameraSettings({ camera }) {
  const busy = camera.status === 'starting';
  const selectedMissing = camera.deviceId && !camera.devices.some(device => device.deviceId === camera.deviceId);
  const active = camera.devices.find(device => device.deviceId === camera.activeDeviceId);
  return <div className="camera-settings">
    <h3 className="settings-subtitle">Camera selection</h3>
    <p className="notice">Choose a built-in or peripheral webcam. Each identified camera gets an app ID such as 0x001 or 0x002.</p>
    <label className="field">Camera device<select value={camera.deviceId} onChange={e => camera.setDeviceId(e.target.value)} disabled={busy}>
      <option value="">System default camera</option>
      {selectedMissing && <option value={camera.deviceId}>Selected camera unavailable — choose another</option>}
      {camera.devices.map((device,index) => <option key={device.deviceId || `hidden-${index}`} value={device.deviceId || `hidden-${index}`} disabled={!device.selectable}>{cameraOptionLabel(device)}</option>)}
    </select></label>
    <button className="text-button" onClick={camera.refreshDevices} disabled={camera.refreshing}><RefreshCw size={13}/>{camera.refreshing ? 'Detecting cameras…' : 'Refresh camera list'}</button>
    <ul className="camera-device-list" aria-label="Detected cameras">{camera.devices.map((device,index) => <li key={device.deviceId || `hidden-${index}`} className={camera.status === 'on' && device.deviceId === camera.activeDeviceId ? 'camera-active' : ''}>
      <code>{device.appId || '—'}</code><span>{device.label || 'Camera name hidden'}<small>{!device.selectable ? 'Allow camera access to identify this device' : camera.status === 'on' && device.deviceId === camera.activeDeviceId ? 'Active camera' : camera.deviceId === device.deviceId ? 'Selected · press Apply / Restart' : 'Available'}</small></span>
    </li>)}</ul>
    {!camera.devices.length && <p className="notice" role="status">No cameras are visible to the browser yet. Connect a webcam and press Start Camera to allow access, then refresh.</p>}
    {camera.devices.some(device => !device.label || !device.selectable) && <p className="notice">Camera names may stay hidden until permission is granted. Press Start Camera and allow access to see the full list.</p>}
    <div className="action-row"><button className="primary" disabled={busy || Boolean(selectedMissing)} onClick={camera.start}><Camera size={16}/>{busy ? 'Connecting…' : camera.status === 'on' ? 'Apply / Restart' : 'Start Camera'}</button><button className="secondary" onClick={camera.stop}>Stop</button></div>
    {camera.status === 'on' && <p className="notice" role="status">Active: {active ? cameraOptionLabel(active) : camera.label}</p>}
    {selectedMissing && <p className="notice" role="status">The selected camera is disconnected or no longer visible. Reconnect it, or select another camera. The app will not silently switch devices.</p>}
    <p className="notice">Select a camera, then press Apply / Restart to use it. IDs are app labels for this session, not USB hardware codes. Built-in cameras and USB webcams both appear here.</p>
  </div>;
}
