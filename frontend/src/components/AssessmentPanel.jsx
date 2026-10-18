import { useState } from 'react';
import { patients } from '../data/patients';
import { checklistLabels, scenarios } from '../lib/simulation';
import { formatDuration } from './SimulationControls';

function Feedback({ title, checklist, events, elapsed }) {
  const pending = checklist.filter(task => !task.done);
  return <div className="assessment-feedback"><h3>{title}</h3><p className="notice">Elapsed: {formatDuration(elapsed)} · {checklist.length-pending.length}/{checklist.length} workflow tasks recorded. This is a completion count, not a clinical score.</p>
    {events.length ? <ol className="event-list">{events.map((event,index) => <li key={index}><time>{formatDuration(event.time)}</time><span>{event.text}</span></li>)}</ol> : <p className="notice">Start the simulation to record actions and receive feedback.</p>}
    <h4>{pending.length ? 'What still needs attention' : 'Workflow checklist complete'}</h4>
    {pending.length ? <ul className="pending-list">{pending.map(task => <li key={task.id}>{task.label}</li>)}</ul> : <p className="notice">All listed workflow actions were recorded. An instructor must review the choices and technique.</p>}
    <p className="notice">Review acknowledgements and written interventions are student-reported. Drug suitability, technique, and intervention quality are not automatically graded.</p>
  </div>;
}

export default function AssessmentPanel({ simulation, dispatch, monitorReady, drug, setDrug, intervention, setIntervention, sensor }) {
  const [tab, setTab] = useState(simulation.lastReport && simulation.status === 'ready' ? 'feedback' : 'checklist');
  const [recognition, setRecognition] = useState('');
  const running = simulation.status === 'running';
  const checklist = Object.entries(checklistLabels).map(([id,label]) => ({ id,label,done: Boolean(simulation.completed[id]) }));
  const report = simulation.lastReport;
  return <>
    <div className="assessment-tabs" role="group" aria-label="Assessment view"><button className={tab === 'checklist' ? 'selected' : ''} aria-pressed={tab === 'checklist'} onClick={() => setTab('checklist')}>Checklist</button><button className={tab === 'feedback' ? 'selected' : ''} aria-pressed={tab === 'feedback'} onClick={() => setTab('feedback')}>Feedback</button></div>
    {tab === 'checklist' ? <>
      <h3 className="assessment-title">Student {simulation.student} · remaining tasks</h3>
      <ul className="task-list">{checklist.map(task => <li className={task.done ? 'done' : ''} key={task.id}><span className="task-symbol" aria-hidden="true">{task.done ? '✓' : '○'}</span><span>{task.label}<small>{task.done ? 'Recorded' : 'To do'}</small></span></li>)}</ul>
      <p className="notice">Review the patient in Patient Info, then initialize the monitor. Use the controls below to record the remaining actions.</p>
      {!running && <p className="notice">Press Start Simulation to begin this student's checklist.</p>}
      <label className="field">Record drug selection<select disabled={!running} value={drug} onChange={e => { setDrug(e.target.value); dispatch({ type: 'drug', value: e.target.value }); }}><option value="">Choose a practice option</option><option>Propofol</option><option>Ketamine</option><option>Alfaxalone</option></select></label>
      <label className="field">Recognize the scripted monitor change<select disabled={!running} value={recognition} onChange={e => setRecognition(e.target.value)}><option value="">Select an observed change</option>{Object.entries(scenarios).filter(([id]) => id !== 'stable').map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <button className="secondary" disabled={!running || !recognition} onClick={() => dispatch({ type: 'recognize', value: recognition, monitorReady })}>Record observation</button>
      {simulation.recognitionMessage && <p className="notice" role="status">{simulation.recognitionMessage}</p>}
      <label className="field intervention-field">Student intervention<textarea disabled={!running} rows="3" placeholder="Describe what you did and why…" value={intervention} onChange={e => setIntervention(e.target.value)}/></label>
      <button className="secondary" disabled={!running || !intervention.trim()} onClick={() => { dispatch({ type: 'intervention', value: intervention }); setTab('feedback'); }}>Record intervention & view feedback</button>
      <dl className="detail-list"><div><dt>Syringe angle</dt><dd>{sensor?.angle_deg == null ? 'No calibrated reading' : `${sensor.angle_deg}°`}</dd></div><div><dt>Administered volume</dt><dd>{sensor?.volume_ml == null ? 'No calibrated reading' : `${sensor.volume_ml} mL`}</dd></div></dl>
    </> : <>
      {(running || !report) && <Feedback title={`Student ${simulation.student} · current actions`} checklist={checklist} events={simulation.events} elapsed={simulation.elapsed}/>}
      {report && <details open={!running} className="completed-report"><summary>Student {report.student} · completed simulation</summary><Feedback title={`Student ${report.student} · ${patients.find(p => p.id === report.patientId)?.Name}`} checklist={report.checklist} events={report.events} elapsed={report.elapsed}/></details>}
      {report && !running && <p className="notice">A different patient is already assigned for Student {simulation.student}. Start Simulation when the next student is ready. This report remains available until that simulation ends.</p>}
    </>}
  </>;
}
