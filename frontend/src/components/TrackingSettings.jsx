import { trackingModes, defaultTrackingAlignment } from '../lib/tracking.js';

export const trackingStatusLabels = {
  idle: 'Tracking paused', connecting: 'Connecting', disconnected: 'Disconnected',
  needs_selection: 'Select pad region', searching: 'Searching for target',
  tracking: 'Target tracked', lost: 'Target lost', error: 'Tracking unavailable',
};

export default function TrackingSettings({ mode, onModeChange, tracking, alignment, setAlignment, onSelectRegion, selecting }) {
  const tracked = mode !== 'normal';
  const metrics = tracking.diagnostics;
  return <section className="tracking-settings" aria-labelledby="tracking-settings-title">
    <h3 className="settings-subtitle" id="tracking-settings-title">Tracking mode</h3>
    <label className="field">Tracking mode<select value={mode} onChange={event => onModeChange(event.target.value)}>
      {trackingModes.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
    </select></label>
    {!tracked ? <p className="notice">Normal mode keeps the current manual dog placement.</p> : <>
      <div className={`tracking-state ${tracking.fresh ? 'is-tracked' : ''}`} role="status">
        <strong>{trackingStatusLabels[tracking.status] || 'Searching for target'}</strong>
        <small>{tracking.status === 'searching' && tracking.detail?.includes('detected') ? 'Waiting for a fresh camera result.' : tracking.detail}</small>
        {Number.isFinite(metrics?.reference_features) && <small>Usable reference points: {metrics.reference_features} / {metrics.required_reference_features} minimum</small>}
        {Number.isFinite(metrics?.reference_coverage) && <small>Point coverage: {Math.round(metrics.reference_coverage * 100)}%{tracking.status === 'needs_selection' ? ' · too concentrated in one area' : ''}</small>}
        {Number.isFinite(metrics?.features) && <small>Tracked points: {metrics.features}</small>}
      </div>
      {mode === 'aruco' ? <p className="notice">Show ArUco marker 0 with its full white margin. The dog appears while the target is tracked.</p>
        : <><p className="notice">Remove printed targets and texture helpers. Select existing details on the original pad.{mode === 'optical-flow' && ' Select again after tracking is lost.'}</p>
          <button id="tracking-select-region" className="secondary full-width" onClick={onSelectRegion} disabled={selecting}>{selecting ? 'Capturing camera…' : 'Select pad region'}</button></>}
      {mode !== 'aruco' && ['needs_selection', 'lost', 'searching'].includes(tracking.status) && <p className="notice">Use a plain background and soft, even light. Move closer and focus on existing vein or channel junctions. A smooth region may not support this method; no printed texture is required or added.</p>}
      {['error', 'disconnected'].includes(tracking.status) && <button className="secondary full-width" onClick={tracking.retry}>Retry tracking</button>}
      <p className="notice">Position, size and screen rotation follow the target. Adjust the dog relative to it below. This is 2D alignment.</p>
      {[
        ['scale', 'Dog width / target width', 0.5, 12, 0.1],
        ['offsetX', 'Horizontal offset (target widths)', -6, 6, 0.1],
        ['offsetY', 'Vertical offset (target widths)', -6, 6, 0.1],
        ['rotation', 'Rotation offset (degrees)', -180, 180, 1],
      ].map(([key, label, min, max, step]) => <label className="field" key={key}>{label}: {alignment[key]}<input type="range" min={min} max={max} step={step} value={alignment[key]} onChange={event => setAlignment({ ...alignment, [key]: Number(event.target.value) })}/></label>)}
      <button className="secondary full-width" onClick={() => setAlignment(defaultTrackingAlignment(mode))}>Reset target alignment</button>
    </>}
  </section>;
}
