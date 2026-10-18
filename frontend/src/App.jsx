import { lazy, Suspense, useEffect, useRef, useState, useReducer } from 'react';
import { Camera, HeartPulse, PawPrint, Settings, Hand, ClipboardCheck, X, Box, Maximize, Eye, ArrowUpRight, Radio } from 'lucide-react';
import { useCamera } from './hooks/useCamera';
import HandOverlay from './components/HandOverlay';
import VitalsControls from './components/VitalsControls';
import CameraSettings from './components/CameraSettings';
import { patients, randomPatientId } from './data/patients';
import { getVitalsState } from './lib/vitals';
import { createSimulation, simulationReducer, simulatedVitals } from './lib/simulation';
import { useMonitorSound } from './hooks/useMonitorSound';
import SimulationControls from './components/SimulationControls';
import MonitorPanel from './components/MonitorPanel';
import AssessmentPanel from './components/AssessmentPanel';

const ModelViewer = lazy(() => import('./components/ModelViewer'));
const tabs = [['patient', PawPrint, 'Patient Info'], ['vitals', HeartPulse, 'Vitals'], ['tracking', Hand, 'Tracking'], ['model', Box, '3D Patient'], ['assessment', ClipboardCheck, 'Assessment'], ['settings', Settings, 'Settings']];

function Toggle({ label, checked, onChange }) {
  return <label className="toggle-row"><span>{label}</span><input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} /><span className="switch" aria-hidden="true" /></label>;
}

export default function App() {
  const video = useRef(null), camera = useCamera(video);
  const [panel, setPanel] = useState('vitals'), [overlays, setOverlays] = useState(true);
  const [tracking, setTracking] = useState(false), [mirrored, setMirrored] = useState(false), [modelVisible, setModelVisible] = useState(true);
  const [handStatus, setHandStatus] = useState('Off'), [backend, setBackend] = useState('Checking backend'), [sensor, setSensor] = useState(null);
  const [drug, setDrug] = useState(''), [intervention, setIntervention] = useState(''), [fullscreen, setFullscreen] = useState(false);
  const [simulation, dispatch] = useReducer(simulationReducer, undefined, createSimulation);
  const patientId = simulation.patientId;
  const [triggerEnabled, setTriggerEnabled] = useState(false);
  const [wireSource, setWireSource] = useState('simulation');
  const [simulatedConnected, setSimulatedConnected] = useState(false);
  const [wireReceivedAt, setWireReceivedAt] = useState(0);
  const [now, setNow] = useState(Date.now);
  const { id: selectedPatientId, ...patient } = patients.find(item => item.id === patientId);
  const vitalsState = getVitalsState({ triggerEnabled, source: wireSource, simulatedConnected, wire: sensor?.wire, now, receivedAt: wireReceivedAt });
  const wireControls = { enabled: triggerEnabled, setEnabled: setTriggerEnabled, source: wireSource, setSource: setWireSource, connected: simulatedConnected, setConnected: setSimulatedConnected, message: vitalsState.message };
  const cameraOn = camera.status === 'on';
  const monitorActive = simulation.status === 'running' && vitalsState.active;
  const vitalValues = simulatedVitals(patientId, simulation.monitored, simulation.scenario, simulation.overrides);
  const sound = useMonitorSound(monitorActive, vitalValues.hr);

  function startSimulation() { dispatch({ type: 'start' }); setPanel('patient'); setOverlays(true); }
  function endSimulation() {
    dispatch({ type: 'end', nextPatientId: randomPatientId(patientId) });
    setDrug(''); setIntervention(''); setSimulatedConnected(false);
    setPanel('assessment'); setOverlays(true);
  }

  useEffect(() => {
    if (simulation.status !== 'running') return;
    let previous = performance.now();
    const timer = setInterval(() => {
      const time = performance.now(), dt = (time-previous)/1000; previous = time;
      if (!document.hidden) dispatch({ type: 'tick', dt, monitorReady: vitalsState.active });
    }, 500);
    return () => clearInterval(timer);
  }, [simulation.status, vitalsState.active]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let active = true, timer, controller;
    async function poll() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2000);
      try {
        const response = await fetch('/api/sensors', { signal: controller.signal });
        if (!response.ok) throw Error();
        const data = await response.json();
        if (active) { setBackend('Backend online'); setSensor(data); setWireReceivedAt(Date.now()); }
      } catch { if (active) { setBackend('Backend offline'); setSensor(null); setWireReceivedAt(0); } }
      finally { clearTimeout(timeout); if (active) timer = setTimeout(poll, 1000); }
    }
    poll();
    return () => { active = false; clearTimeout(timer); controller?.abort(); };
  }, []);
  useEffect(() => {
    const update = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', update);
    return () => document.removeEventListener('fullscreenchange', update);
  }, []);
  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch { camera.setError('Full-screen mode is unavailable in this browser window.'); }
  }
  function openPanel(id) { setOverlays(true); setPanel(current => current === id && overlays ? '' : id); }

  return <main className={`app ${cameraOn ? 'is-live' : ''}`}>
    <video ref={video} className={`camera-feed ${mirrored ? 'mirrored' : ''}`} playsInline muted autoPlay aria-label="Live real-world camera" />
    <HandOverlay videoRef={video} enabled={cameraOn && tracking && overlays} mirrored={mirrored} onStatus={setHandStatus} />
    <div className="edge-shade" aria-hidden="true" />
    <header className="header"><a className="brand" href="#" onClick={e => { e.preventDefault(); openPanel('patient'); }} aria-label="Open patient information"><span className="brand-mark"><PawPrint size={24}/></span><span><strong>VET<span className="mint-text">/</span>AR</strong><small>ANESTHESIA SIMULATION LAB</small></span></a><div className="session-label"><span className="tiny-label">TRAINING WORKSPACE</span><span>Canine intravenous procedure <ArrowUpRight size={13}/></span></div><div className={`status-pill ${cameraOn ? 'live' : ''}`} role="status"><span className="dot"/>{cameraOn ? 'LIVE CAMERA' : camera.status === 'starting' ? 'CONNECTING' : 'CAMERA OFF'}</div></header>
    <nav className="navigation" aria-label="Workspace panels">{tabs.map(([id, Icon, label]) => <button key={id} className={panel === id && overlays ? 'nav-active' : ''} onClick={() => openPanel(id)} aria-pressed={panel === id && overlays}><Icon size={18}/><span>{label}</span></button>)}<div className="nav-spacer"/><button title="Toggle AR overlays" aria-label="Toggle AR overlays" aria-pressed={overlays} onClick={() => setOverlays(x => !x)}><Eye size={18}/></button><button title="Toggle full screen" aria-label="Toggle full screen" onClick={toggleFullscreen}><Maximize size={18}/></button></nav>
    <SimulationControls simulation={simulation} patient={patient} onStart={startSimulation} onEnd={endSimulation}/>
    {!cameraOn && <div className={`camera-placeholder ${panel && overlays ? 'with-panel' : ''}`}><div className="camera-emblem"><Camera size={32}/></div><span className="eyebrow">YOUR REAL WORLD. AUGMENTED.</span><h1>A new perspective<br/>on clinical training.</h1><p>Connect your camera to bring the simulation<br/>into your practice space.</p><button className="primary" disabled={camera.status === 'starting'} onClick={camera.start}><Camera size={17}/>{camera.status === 'starting' ? 'Waiting for camera…' : 'Start Camera'}<ArrowUpRight size={16}/></button><small>USB & built-in webcams supported · video stays in your browser</small></div>}
    {overlays && <><aside className="patient-chip"><span className="patient-avatar"><PawPrint size={20}/></span><span><strong>{patient.Name} <span>CANINE PATIENT</span></strong><small>{patient.Breed} · {patient.Sex} · {patient.Weight}</small></span><span className="patient-condition">SIMULATED</span></aside>
    {cameraOn && <div className="viewfinder" aria-hidden="true"><i/><i/><i/><i/><span>CAMERA OVERLAY · NO SPATIAL ANCHOR</span></div>}
    {panel && <section className="panel" aria-label={tabs.find(t => t[0] === panel)?.[2]}><div className="panel-header"><div><span className="eyebrow">SIMULATION WORKSPACE</span><h2>{tabs.find(t => t[0] === panel)?.[2]}</h2></div><button className="icon-button" aria-label="Collapse panel" onClick={() => setPanel('')}><X size={18}/></button></div>
    {panel === 'vitals' && <><details className="demo-controls wire-settings"><summary>Wire activation settings</summary><VitalsControls {...wireControls}/></details><MonitorPanel simulation={simulation} dispatch={dispatch} values={vitalValues} active={monitorActive} sound={sound}/></>}
    {panel === 'patient' && <><span className="badge">ASSIGNED PATIENT · STUDENT {simulation.student}</span><p className="notice">Patient information is fixed for this simulation. A different patient is randomly assigned only when you end it.</p><div className="patient-heading"><span className="patient-avatar large"><PawPrint size={30}/></span><div><h3>Meet {patient.Name}</h3><p>Your virtual training patient</p></div></div><dl className="detail-list">{Object.entries(patient).map(([name,value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl><button className="secondary full-width" disabled={simulation.status !== 'running' || simulation.completed.patient} onClick={() => dispatch({ type: 'review' })}>{simulation.completed.patient ? 'Patient review recorded' : 'Confirm patient reviewed'}</button></>}
    {panel === 'tracking' && <><p className="notice">Detect up to two hands with 21 landmarks per hand. Tracking runs locally in a background worker.</p><Toggle label="Hand skeleton overlay" checked={tracking} onChange={setTracking}/><div className="connection-card"><Hand size={21}/><div><strong>{handStatus}</strong><small>{cameraOn ? 'Camera is ready' : 'Start the camera to begin tracking'}</small></div></div><p className="notice">Hand landmarks visualize movement; they do not measure syringe insertion angle. Internet is required to download tracker assets.</p></>}
    {panel === 'model' && <><Toggle label="3D model visibility" checked={modelVisible} onChange={setModelVisible}/>{modelVisible && <Suspense fallback={<p className="notice">Loading 3D viewer…</p>}><ModelViewer/></Suspense>}<p className="notice">Virtual patient viewer only. Marker anchoring and React Three Fiber integration are planned for Phase 7.</p></>}
    {panel === 'assessment' && <AssessmentPanel key={simulation.student} simulation={simulation} dispatch={dispatch} monitorReady={monitorActive} drug={drug} setDrug={setDrug} intervention={intervention} setIntervention={setIntervention} sensor={sensor}/>}
    {panel === 'settings' && <><h3 className="settings-subtitle">Monitor sound</h3><button className="secondary full-width" aria-pressed={sound.enabled} onClick={sound.toggle}>{sound.enabled ? 'Mute heartbeat beep' : 'Enable heartbeat beep'}</button>{sound.error && <p className="notice" role="status">{sound.error}</p>}<h3 className="settings-subtitle sound-settings">Vitals activation</h3><VitalsControls {...wireControls}/><CameraSettings camera={camera}/><h3 className="settings-subtitle">Overlay controls</h3><Toggle label="Mirror camera & skeleton" checked={mirrored} onChange={setMirrored}/><Toggle label="Hand skeleton overlay" checked={tracking} onChange={setTracking}/><Toggle label="AR overlays" checked={overlays} onChange={setOverlays}/><Toggle label="3D model visibility" checked={modelVisible} onChange={setModelVisible}/><button className="secondary full-width" onClick={toggleFullscreen}><Maximize size={16}/>{fullscreen ? 'Exit full screen' : 'Enter full screen'}</button><div className="connection-card"><Radio size={20}/><div><strong>{backend}</strong><small>{sensor?.status || 'Hardware not connected'}</small></div></div><button className="secondary full-width" disabled>Sensor calibration · awaiting hardware</button><p className="notice">Calibration must establish syringe-axis and skin-plane alignment plus volume units. Raw pitch difference is not a validated insertion angle.</p></>}
    </section>}<div className="workspace-note"><span className="tiny-label">GUIDED PRACTICE / 01</span><strong>Prepare. Observe. Assess.</strong><span>Training prototype · expert review pending</span></div></>}
    {camera.error && <div className="error" role="alert"><span>{camera.error}</span><button className="icon-button" aria-label="Dismiss error" onClick={() => camera.setError('')}><X size={18}/></button></div>}
    <footer><span><span className={`dot ${cameraOn ? 'live-dot' : ''}`}/>{cameraOn ? camera.label : 'CAMERA STANDBY'}</span><span className="footer-tracking"><Hand size={13}/> {handStatus}</span><span>{backend}<span className="footer-divider">/</span>{sensor?.status || 'Hardware not connected'}</span>{cameraOn && <button className="text-button" onClick={camera.stop}>Stop Camera</button>}</footer>
  </main>;
}
