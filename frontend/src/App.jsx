import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Camera, HeartPulse, PawPrint, Settings, Hand, ClipboardCheck, X, Box, Maximize, Eye, ArrowUpRight, Radio, Activity } from 'lucide-react';
import { useCamera } from './hooks/useCamera';
import { useAssessment } from './hooks/useAssessment';
import { useMonitorSound } from './hooks/useMonitorSound';
import { patients } from './data/patients';
import { getVitalsState } from './lib/vitals';
import { phaseNames, scenarioName, formatSeconds } from './lib/assessmentView';
import HandOverlay from './components/HandOverlay';
import VitalsControls from './components/VitalsControls';
import CameraSettings from './components/CameraSettings';
import SimulationControls from './components/SimulationControls';
import MonitorPanel from './components/MonitorPanel';
import AssessmentPanel from './components/AssessmentPanel';
import ModeSelection from './components/ModeSelection';
import ScenarioPanel from './components/ScenarioPanel';
import HardwarePanel from './components/HardwarePanel';
import InjectionAngle from './components/InjectionAngle';
import InterventionNotice from './components/InterventionNotice';

const ModelViewer = lazy(() => import('./components/ModelViewer'));
const tabs = [['patient', PawPrint, 'Patient Info'], ['vitals', HeartPulse, 'Vitals'], ['scenario', Activity, 'Scenario'], ['hardware', Radio, 'Hardware'], ['assessment', ClipboardCheck, 'Assessment'], ['tracking', Hand, 'Tracking'], ['model', Box, '3D Patient'], ['settings', Settings, 'Settings']];

function Toggle({ label, checked, onChange }) {
  return <label className="toggle-row"><span>{label}</span><input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)}/><span className="switch" aria-hidden="true"/></label>;
}

export default function App() {
  const video = useRef(null), camera = useCamera(video), assessment = useAssessment();
  const state = assessment.state;
  const [panel, setPanel] = useState(''), [overlays, setOverlays] = useState(true);
  const [tracking, setTracking] = useState(false), [mirrored, setMirrored] = useState(false), [modelVisible, setModelVisible] = useState(true);
  const [handStatus, setHandStatus] = useState('Off'), [fullscreen, setFullscreen] = useState(false);
  const [triggerEnabled, setTriggerEnabled] = useState(false), [wireSource, setWireSource] = useState('simulation'), [simulatedConnected, setSimulatedConnected] = useState(false);
  const [now, setNow] = useState(Date.now), [dismissedNotice, setDismissedNotice] = useState(null);
  const patient = patients.find(item => item.id === state?.patient_id) || patients[0];
  const menu = !state || state.phase === 'mode_selection';
  const disabled = assessment.busy || !assessment.connected;
  const gate = getVitalsState({ triggerEnabled, source: wireSource, simulatedConnected, wire: state?.wire, now, receivedAt: assessment.receivedAt });
  const wireControls = { enabled: triggerEnabled, setEnabled: setTriggerEnabled, source: wireSource, setSource: setWireSource, connected: simulatedConnected, setConnected: setSimulatedConnected, message: gate.message };
  const monitorActive = Boolean(state?.mode && assessment.connected && gate.active);
  const values = state?.vitals || { hr: 0, rr: 0, spo2: 0, map: 0, etco2: 0, temp: 0 };
  const sound = useMonitorSound(monitorActive, values.hr);
  const notice = state?.notification && state.notification.id !== dismissedNotice ? state.notification : null;
  const cameraOn = camera.status === 'on';

  async function act(action, fields) {
    const result = await assessment.command(action, fields);
    if (!result) return null;
    if (action === 'select_mode') { setPanel('patient'); setOverlays(true); }
    if (action === 'begin_injection') { setPanel('hardware'); setOverlays(true); }
    if (action === 'start_scenario' || action === 'complete_injection' || action === 'complete_non_injectable_intervention') { setPanel(result.phase === 'evaluated' ? 'assessment' : 'vitals'); setOverlays(true); }
    if (action === 'end') { setSimulatedConnected(false); setPanel('assessment'); setOverlays(true); }
    return result;
  }

  useEffect(() => {
    if (state?.phase === 'intervention_injection') { setPanel('hardware'); setOverlays(true); }
  }, [state?.phase, state?.injection_stage_id]);

  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(timer); }, []);
  useEffect(() => {
    const update = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', update);
    return () => document.removeEventListener('fullscreenchange', update);
  }, []);
  async function toggleFullscreen() {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); }
    catch { camera.setError('Full-screen mode is unavailable in this browser window.'); }
  }
  function openPanel(id) { setOverlays(true); setPanel(current => current === id && overlays ? '' : id); }

  return <main className={`app ${cameraOn ? 'is-live' : ''} ${menu ? 'menu-workspace' : ''}`}>
    <video ref={video} className={`camera-feed ${mirrored ? 'mirrored' : ''}`} playsInline muted autoPlay aria-label="Live real-world camera"/>
    <HandOverlay videoRef={video} enabled={cameraOn && tracking && overlays} mirrored={mirrored} onStatus={setHandStatus}/>
    <div className="edge-shade" aria-hidden="true"/>
    <header className="header"><a className="brand" href="#" onClick={e => { e.preventDefault(); openPanel('patient'); }} aria-label="Open patient information"><span className="brand-mark"><PawPrint size={24}/></span><span><strong>VET<span className="mint-text">/</span>AR</strong><small>ANESTHESIA SIMULATION LAB</small></span></a><div className="session-label"><span className="tiny-label">TWO-MODE ASSESSMENT STATION</span><span>Canine procedure & intervention <ArrowUpRight size={13}/></span></div><div className={`status-pill ${cameraOn ? 'live' : ''}`} role="status"><span className="dot"/>{cameraOn ? 'LIVE CAMERA' : camera.status === 'starting' ? 'CONNECTING' : 'CAMERA OFF'}</div></header>
    <nav className="navigation" aria-label="Workspace panels">{tabs.map(([id,Icon,label]) => <button key={id} className={panel === id && overlays ? 'nav-active' : ''} onClick={() => openPanel(id)} aria-pressed={panel === id && overlays}><Icon size={17}/><span>{label}</span></button>)}<div className="nav-spacer"/><button title="Toggle AR overlays" aria-label="Toggle AR overlays" aria-pressed={overlays} onClick={() => setOverlays(x => !x)}><Eye size={18}/></button><button title="Toggle full screen" aria-label="Toggle full screen" onClick={toggleFullscreen}><Maximize size={18}/></button></nav>
    <SimulationControls state={state} patient={patient} busy={assessment.busy} connected={assessment.connected} onAction={act}/>
    {state?.scenario_id && <section className="active-scenario-banner" aria-label="Visible complication"><span><b>{scenarioName(state)}</b><small>{phaseNames[state.phase]} · SIMULATED</small></span><span>HR {monitorActive ? values.hr : '—'} · MAP {monitorActive ? values.map : '—'} · RR {monitorActive ? values.rr : '—'} · EtCO₂ {monitorActive ? values.etco2 : '—'}</span><span>{state.first_response_seconds == null ? state.scenario_elapsed == null ? 'Preparing response timer' : `Response timer ${formatSeconds(state.scenario_elapsed)}` : `First response ${formatSeconds(state.first_response_seconds)}`}</span></section>}
    {menu && <ModeSelection connected={assessment.connected} busy={assessment.busy} onSelect={mode => act('select_mode', { mode })} onRetry={assessment.retryConnection} withPanel={Boolean(panel && overlays)}/>}
    {!menu && !cameraOn && !state?.injection_stage_id && <div className={`camera-placeholder ${panel && overlays ? 'with-panel' : ''}`}><div className="camera-emblem"><Camera size={32}/></div><span className="eyebrow">YOUR REAL WORLD. AUGMENTED.</span><h1>Your training space.<br/>Your next response.</h1><p>The assessment works without a webcam.<br/>Enable it for the AR overlay experience.</p><button className="primary" disabled={camera.status === 'starting'} onClick={camera.start}><Camera size={17}/>{camera.status === 'starting' ? 'Waiting for camera…' : 'Start Camera'}</button></div>}
    {overlays && <>
      <InjectionAngle state={state} floating/>
      {!menu && <aside className="patient-chip"><span className="patient-avatar"><PawPrint size={20}/></span><span><strong>{patient.Name}<span>ASSIGNED PATIENT</span></strong><small>{patient.Breed} · {patient.Sex} · {patient.Weight}</small></span><span className="patient-condition">SIMULATED</span></aside>}
      {panel && <section className="panel" aria-label={tabs.find(t => t[0] === panel)?.[2]}><div className="panel-header"><div><span className="eyebrow">SIMULATION WORKSPACE</span><h2>{tabs.find(t => t[0] === panel)?.[2]}</h2></div><button className="icon-button" aria-label="Collapse panel" onClick={() => setPanel('')}><X size={18}/></button></div>
        {panel === 'patient' && (menu ? <p className="notice">Choose an assessment mode to view the next student's assigned patient.</p> : <><span className="badge">ASSIGNED PATIENT · STUDENT {state.student}</span><p className="notice">This patient's information stays fixed until End Assessment.</p><div className="patient-heading"><span className="patient-avatar large"><PawPrint size={30}/></span><div><h3>Meet {patient.Name}</h3><p>Your fictional training patient</p></div></div><dl className="detail-list">{Object.entries(patient).filter(([key]) => key !== 'id').map(([name,value]) => <div key={name}><dt>{name === 'Condition' ? 'Baseline condition' : name}</dt><dd>{value}</dd></div>)}</dl><button className="secondary full-width" disabled={disabled || state.checklist.patient || state.phase === 'evaluated'} onClick={() => act('review')}>{state.checklist.patient ? 'Patient review recorded' : 'Confirm patient reviewed'}</button></>)}
        {panel === 'vitals' && <><details className="demo-controls wire-settings"><summary>Optional wire activation settings</summary><VitalsControls {...wireControls}/></details><MonitorPanel state={state} values={values} active={monitorActive} sound={sound}/></>}
        {panel === 'scenario' && <ScenarioPanel state={state} command={act} disabled={disabled}/>}
        {panel === 'hardware' && <HardwarePanel state={state} command={act} disabled={disabled}/>}
        {panel === 'assessment' && <AssessmentPanel key={state?.session_id || `menu-${state?.student}`} state={state} command={act} disabled={disabled}/>}
        {panel === 'tracking' && <><p className="notice">Pretrained MediaPipe hand tracking runs locally in a browser worker, up to two hands and 21 landmarks per hand.</p><Toggle label="Hand skeleton overlay" checked={tracking} onChange={setTracking}/><div className="connection-card"><Hand size={21}/><div><strong>{handStatus}</strong><small>{cameraOn ? 'Camera is ready' : 'Start the camera in Settings'}</small></div></div><p className="notice">Hands visualize motion only; they do not measure syringe angle or injection completion. Internet is needed for the model/runtime download.</p></>}
        {panel === 'model' && <><Toggle label="3D model visibility" checked={modelVisible} onChange={setModelVisible}/>{modelVisible && <Suspense fallback={<p className="notice">Loading 3D viewer…</p>}><ModelViewer/></Suspense>}<p className="notice">Optional GLB viewer. Physical dummy anchoring is not implemented yet.</p></>}
        {panel === 'settings' && <><h3 className="settings-subtitle">Monitor sound</h3><button className="secondary full-width" aria-pressed={sound.enabled} onClick={sound.toggle}>{sound.enabled ? 'Mute heartbeat beep' : 'Enable heartbeat beep'}</button>{sound.error && <p className="notice" role="status">{sound.error}</p>}<h3 className="settings-subtitle sound-settings">Optional wire activation</h3><VitalsControls {...wireControls}/><CameraSettings camera={camera}/><h3 className="settings-subtitle">Overlay controls</h3><Toggle label="Mirror camera & skeleton" checked={mirrored} onChange={setMirrored}/><Toggle label="Hand skeleton overlay" checked={tracking} onChange={setTracking}/><Toggle label="AR overlays" checked={overlays} onChange={setOverlays}/><Toggle label="3D model visibility" checked={modelVisible} onChange={setModelVisible}/><button className="secondary full-width" onClick={toggleFullscreen}><Maximize size={16}/>{fullscreen ? 'Exit full screen' : 'Enter full screen'}</button><div className="connection-card"><Radio size={20}/><div><strong>{assessment.connected ? 'Backend online' : 'Backend offline'}</strong><small>Assessment state / RFID / timing are managed by FastAPI.</small></div></div><p className="notice">Use Hardware to choose simulated or ESP32 input before starting a procedure. Calibration transforms and real interventions require validation.</p></>}
      </section>}
    </>}
    {notice && <InterventionNotice key={notice.id} notice={notice} state={state} onDismiss={() => setDismissedNotice(notice.id)} onContinue={() => { setDismissedNotice(notice.id); setPanel(state.phase === 'intervention_injection' ? 'hardware' : state.phase === 'intervention_review' || state.phase === 'intervention_non_injectable' ? 'scenario' : 'assessment'); setOverlays(true); }}/>}
    {(camera.error || assessment.error) && <div className="error" role="alert"><span>{[camera.error, assessment.error].filter(Boolean).join(' ')}</span><button className="icon-button" aria-label="Dismiss error" onClick={() => { camera.setError(''); assessment.setError(''); }}><X size={18}/></button></div>}
    <footer><span><span className={`dot ${cameraOn ? 'live-dot' : ''}`}/>{cameraOn ? camera.label : 'CAMERA STANDBY'}</span><span className="footer-tracking"><Hand size={13}/> {handStatus}</span><span>{assessment.connected ? 'Backend online' : 'Backend offline'}<span className="footer-divider">/</span>{state?.input_source === 'esp32' ? state.hardware.esp32_connected ? 'ESP32 connected' : 'ESP32 disconnected' : 'Simulated hardware'}</span>{cameraOn && <button className="text-button" onClick={camera.stop}>Stop Camera</button>}</footer>
  </main>;
}
