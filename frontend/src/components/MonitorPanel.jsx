import { monitorChannels } from '../lib/monitor';
import { scenarioName } from '../lib/assessmentView';
import Waveform from './Waveform';

export default function MonitorPanel({ state, values, active, sound }) {
  const targets = state?.catalog?.scenarios?.[state.scenario_id]?.target || {};
  return <><div className="monitor-heading"><span className="badge">SIMULATED SIGNALS</span><button className="secondary" onClick={sound.toggle} aria-pressed={sound.enabled}>{sound.enabled ? 'Mute beep' : 'Enable beep'}</button></div>
    {sound.error && <p className="notice" role="status">{sound.error}</p>}
    <p className="monitor-status" role="status">{!state?.mode ? 'Choose an assessment mode to view baseline vitals.' : !active ? 'Monitor paused · check backend / wire connection' : scenarioName(state)}</p>
    <div className="monitor-grid">{monitorChannels.map(channel => <div className={`monitor-channel ${channel.color} ${active ? '' : 'monitor-paused'}`} key={channel.key}><div className="channel-label"><span>{channel.label}</span><strong>{active ? Number(values[channel.key]).toFixed(channel.key === 'temp' ? 1 : 0) : '—'} <small>{channel.unit}</small></strong></div>{targets[channel.key] != null && <small>Scenario target: {targets[channel.key]} {channel.unit}</small>}<Waveform channel={channel.key} values={values} active={active}/></div>)}</div>
    <p className="notice">One scripted complication stays active until assessment evaluation or ending. Incorrect RFID selections do not change the vital-sign targets. Waveforms and all values are simulated; no clinical measurements are shown.</p>
  </>;
}
