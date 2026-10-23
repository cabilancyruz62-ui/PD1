import { monitorChannels } from '../lib/monitor';
import { scenarioName } from '../lib/assessmentView';
import Waveform from './Waveform';

export default function MonitorPanel({ state, values, active, sound, pauseReason, onControls }) {
  return <><div className="monitor-heading" style={{ justifyContent: onControls ? 'space-between' : 'flex-end' }}>{onControls && <button className="text-button" onClick={onControls}>Monitor controls</button>}<button className="secondary" onClick={sound.toggle} aria-pressed={sound.enabled}>{sound.enabled ? 'Mute beep' : 'Enable beep'}</button></div>
    {sound.error && <p className="notice" role="status">{sound.error}</p>}
    <p className="monitor-status" role="status">{!state?.mode ? 'Choose an assessment mode to view baseline vitals.' : !active ? pauseReason || 'Monitor paused · check backend / wire connection' : state.scenario_id ? scenarioName(state) : 'Baseline'}</p>
    <div className="monitor-grid">{monitorChannels.map(channel => {
      return <div className={`monitor-channel ${channel.color} ${active ? '' : 'monitor-paused'}`} key={channel.key}>
        <div className="channel-label"><span>{channel.label}</span><strong>{active ? Number(values[channel.key]).toFixed(channel.key === 'temp' ? 1 : 0) : '—'} <small>{channel.unit}</small></strong></div>
        <Waveform channel={channel.key} values={values} active={active}/>
      </div>;
    })}</div>
  </>;
}
