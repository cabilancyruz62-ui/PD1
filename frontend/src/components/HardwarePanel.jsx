import { useState } from 'react';
import InjectionAngle from './InjectionAngle';
import { getAngleFeedback } from '../lib/feedback';

export default function HardwarePanel({ state, command, disabled }) {
  const [uid, setUid] = useState('RFID_TAG_001');
  if (!state) return <p className="notice">Waiting for the backend.</p>;
  const hw = state.hardware, angle = state.angle;
  const simulation = state.input_source === 'simulation';
  const injectionActive = ['injection', 'intervention_injection'].includes(state.phase);
  const canTest = !disabled && Boolean(state.mode) && simulation;
  const angleFeedback = getAngleFeedback(state);
  const validAngle = (state.catalog.angle_min_deg + state.catalog.angle_max_deg) / 2;
  const lowAngle = Math.max(0, state.catalog.angle_min_deg - 5);
  const highAngle = Math.min(90, state.catalog.angle_max_deg + 15);
  return <><label className="field">Hardware input source<select value={state.input_source} disabled={disabled || state.phase !== 'preparation'} onChange={e => command('configure', { input_source: e.target.value })}><option value="simulation">SIMULATED · no ESP32 required</option><option value="esp32">REAL · ESP32 hardware</option></select></label>
    <span className="badge">{simulation ? 'SIMULATED HARDWARE INPUT' : 'ESP32 HARDWARE INPUT'}</span><InjectionAngle state={state}/><dl className="detail-list">{[['ESP32',hw.esp32_connected],['MPU6050',hw.mpu_connected],['RFID reader',hw.rfid_connected]].map(([name,connected]) => <div key={name}><dt>{name}</dt><dd>{connected ? 'Connected' : 'Disconnected / stale'}</dd></div>)}<div><dt>Current syringe angle</dt><dd>{angle?.fresh && angle.angle_deg != null ? `${angle.angle_deg}°` : 'No fresh reading'}</dd></div><div><dt>Calibration</dt><dd>{angle?.calibrated && angle.calibration_id ? angle.calibration_id : 'Not calibrated'}</dd></div><div><dt>Prototype target</dt><dd>{state.catalog.angle_min_deg}°–{state.catalog.angle_max_deg}°</dd></div><div><dt>Angle result</dt><dd>{angleFeedback?.title || 'Not assessable'}</dd></div><div><dt>Last RFID UID</dt><dd>{state.last_tag?.uid || 'No tag detected'}</dd></div><div><dt>Last read source</dt><dd>{state.last_tag?.source || '—'}</dd></div></dl>
    {hw.error && <p className="notice" role="alert">{hw.error}</p>}
    <details className="demo-controls" open={simulation}><summary>Simulation controls · testing only</summary><p className="notice">Test inputs only. No sensor readings.</p><div className="test-grid"><button className="secondary" disabled={!canTest || !injectionActive} onClick={() => command('simulate_angle', { angle_deg: validAngle })}>Valid angle · {validAngle}°</button><button className="secondary" disabled={!canTest || !injectionActive || state.catalog.angle_min_deg === 0} onClick={() => command('simulate_angle', { angle_deg: lowAngle })}>Low angle · {lowAngle}°</button><button className="secondary" disabled={!canTest || !injectionActive || state.catalog.angle_max_deg === 90} onClick={() => command('simulate_angle', { angle_deg: highAngle })}>High angle · {highAngle}°</button><button className="secondary" disabled={!canTest} onClick={() => command('simulate_rfid', { scan_kind: 'correct' })}>Correct RFID tag</button><button className="secondary" disabled={!canTest} onClick={() => command('simulate_rfid', { scan_kind: 'incorrect' })}>Incorrect RFID tag</button><button className="secondary" disabled={!canTest} onClick={() => command('simulate_rfid', { scan_kind: 'unregistered' })}>Unregistered tag</button><button className="secondary" disabled={!canTest || !state.rfid_events.length} onClick={() => command('simulate_rfid', { scan_kind: 'duplicate' })}>Repeat last event</button><button className="secondary" disabled={!canTest} onClick={() => command('simulate_disconnect')}>Disconnect sensors</button><button className="secondary" disabled={!canTest} onClick={() => command('simulate_reconnect')}>Reconnect sensors</button></div><label className="field">Test RFID UID<input value={uid} maxLength={128} onChange={e => setUid(e.target.value)}/></label><button className="secondary" disabled={!canTest || !uid.trim()} onClick={() => command('simulate_rfid', { uid: uid.trim() })}>Submit UID</button></details>
    <p className="notice">Calibrate to the dummy surface. Target range requires expert review.</p>
  </>;
}
