import { monitorChannels, scenarios } from '../lib/simulation';
import Waveform from './Waveform';

export default function MonitorPanel({ simulation, dispatch, values, active, sound }) {
  const running = simulation.status === 'running';
  return <>
    <div className="monitor-heading"><span className="badge">SIMULATED SIGNALS</span><button className="secondary" onClick={sound.toggle} aria-pressed={sound.enabled}>{sound.enabled ? 'Mute beep' : 'Enable beep'}</button></div>
    {sound.error && <p className="notice" role="status">{sound.error}</p>}
    <p className="monitor-status" role="status">{!running ? 'Start Simulation to initialize the monitor.' : active ? `${scenarios[simulation.scenario]} · monitor running` : 'Monitor paused · waiting for wire connection'}</p>
    <div className="monitor-grid">{monitorChannels.map(channel => <div className={`monitor-channel ${channel.color} ${active ? '' : 'monitor-paused'}`} key={channel.key}>
      <div className="channel-label"><span>{channel.label}</span><strong>{active ? values[channel.key].toFixed(channel.key === 'temp' ? 1 : 0) : '—'} <small>{channel.unit}</small></strong></div>
      <Waveform channel={channel.key} values={values} active={active}/>
    </div>)}</div>
    <details className="demo-controls"><summary>Simulation controls</summary><p className="notice">Illustrative effects only. Low RR shrinks and slows the respiratory trace; high RR enlarges and speeds it up. Each other channel has its own signal shape. Temperature shows a slow trend.</p>
      <label className="field">Demo condition<select disabled={!running} value={simulation.scenario} onChange={e => dispatch({ type: 'scenario', value: e.target.value })}>{Object.entries(scenarios).map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label className="toggle-row"><span>Auto-cycle demo every 30 monitored seconds</span><input type="checkbox" disabled={!running} checked={simulation.auto} onChange={e => dispatch({ type: 'auto', value: e.target.checked })}/><span className="switch" aria-hidden="true"/></label>
      {monitorChannels.map(channel => <label className="range-control" key={channel.key}><span>{channel.label}<b>{values[channel.key]} {channel.unit}</b></span><input aria-label={`Simulate ${channel.label}`} type="range" min={channel.min} max={channel.max} step={channel.step || 1} disabled={!running} value={values[channel.key]} onChange={e => dispatch({ type: 'override', key: channel.key, value: Number(e.target.value) })}/></label>)}
    </details>
    <p className="notice">Artificial monitor signals for practice. Waveform height is a visual effect, not a diagnostic measurement. Sliders do not simulate validated drug effects.</p>
  </>;
}
