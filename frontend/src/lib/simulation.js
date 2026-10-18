import { patients } from '../data/patients.js';

// These are deliberately illustrative demo conditions, not clinical assessment rules.
export const scenarios = {
  stable: 'Baseline',
  slow: 'Reduced respiration',
  exaggerated: 'Exaggerated activity',
  recovery: 'Recovery',
};
export const checklistLabels = {
  patient: 'Review the assigned patient',
  monitor: 'Initialize the vital-sign monitor',
  drug: 'Record a drug selection',
  recognition: 'Identify a simulated vital-sign change',
  intervention: 'Record your intervention',
};

export function createSimulation(patientId = patients[Math.floor(Math.random() * patients.length)].id) {
  return { patientId, student: 1, status: 'ready', elapsed: 0, monitored: 0, scenario: 'stable', auto: true, overrides: {}, completed: {}, events: [], lastReport: null, recognitionMessage: '' };
}

function log(state, task, text, extra = {}) {
  return { ...state, ...extra, completed: { ...state.completed, [task]: true }, events: [...state.events, { time: state.elapsed, text }].slice(-100) };
}

export function simulationReducer(state, action) {
  if (action.type === 'start' && state.status === 'ready') return { ...state, status: 'running', events: [{ time: 0, text: `Student ${state.student} started the simulation.` }] };
  if (state.status !== 'running') return state;
  switch (action.type) {
    case 'tick': {
      const dt = Math.max(0, Math.min(action.dt, 2));
      let next = { ...state, elapsed: state.elapsed + dt, monitored: state.monitored + (action.monitorReady ? dt : 0) };
      if (action.monitorReady && !state.completed.monitor) next = log(next, 'monitor', 'Initialized the simulated vital-sign monitor.');
      if (state.auto) {
        const scenario = ['stable', 'slow', 'exaggerated', 'recovery'][Math.floor(next.monitored / 30) % 4];
        if (scenario !== state.scenario) next = { ...next, scenario, overrides: {}, recognitionMessage: '', events: [...next.events, { time: next.elapsed, text: `Demo condition changed: ${scenarios[scenario]}.` }] };
      }
      return next;
    }
    case 'review': return state.completed.patient ? state : log(state, 'patient', 'Confirmed reviewing the assigned patient information.');
    case 'drug': return action.value ? log(state, 'drug', `Recorded drug selection: ${action.value}. Suitability is not graded.`) : state;
    case 'intervention': return action.value?.trim() ? log(state, 'intervention', `Recorded intervention: ${action.value.trim()}`) : state;
    case 'scenario': return scenarios[action.value] ? { ...state, scenario: action.value, auto: false, overrides: {}, recognitionMessage: '', events: [...state.events, { time: state.elapsed, text: `Selected demo condition: ${scenarios[action.value]}.` }] } : state;
    case 'auto': return { ...state, auto: action.value, overrides: {} };
    case 'override': return Number.isFinite(action.value) ? { ...state, auto: false, overrides: { ...state.overrides, [action.key]: action.value } } : state;
    case 'recognize': {
      if (!action.monitorReady) return { ...state, recognitionMessage: 'Initialize the monitor before identifying a change.' };
      if (state.scenario === 'stable') return { ...state, recognitionMessage: 'No scripted change yet. Wait for a demo condition or select one in Vitals.' };
      if (action.value !== state.scenario) return { ...state, recognitionMessage: 'That does not match the current scripted condition. Recheck the monitor.', events: [...state.events, { time: state.elapsed, text: `Recognition attempt: ${scenarios[action.value] || 'No selection'}; did not match the scripted condition.` }] };
      return log(state, 'recognition', `Identified the scripted condition: ${scenarios[action.value]}.`, { recognitionMessage: 'Matched the scripted condition. This checks observation, not a clinical diagnosis.' });
    }
    case 'end': {
      const completed = Object.keys(checklistLabels).map(id => ({ id, label: checklistLabels[id], done: Boolean(state.completed[id]) }));
      const report = { student: state.student, patientId: state.patientId, elapsed: state.elapsed, checklist: completed, events: [...state.events, { time: state.elapsed, text: 'Ended the simulation and prepared the next patient.' }] };
      const next = action.nextPatientId && action.nextPatientId !== state.patientId && patients.some(p => p.id === action.nextPatientId) ? action.nextPatientId : patients.find(p => p.id !== state.patientId).id;
      return { ...createSimulation(next), student: state.student + 1, lastReport: report };
    }
    default: return state;
  }
}

export function simulatedVitals(patientId, time, scenario = 'stable', overrides = {}) {
  const i = Math.max(0, patients.findIndex(p => p.id === patientId));
  const base = { hr: 86 + i * 2, rr: 18 + i % 5, spo2: 98, map: 88 + i, etco2: 37 + i % 3, temp: 38.3 + i % 3 * .1 };
  const targets = {
    stable: base,
    slow: { ...base, hr: 64 + i, rr: 6, spo2: 90, map: 62, etco2: 52, temp: 37.2 },
    exaggerated: { hr: 150 + i, rr: 40, spo2: 95, map: 125, etco2: 28, temp: 39.5 },
    recovery: { ...base, hr: base.hr + 5, rr: 16, spo2: 97 },
  };
  const target = targets[scenario] || base;
  const result = {};
  for (const [key,value] of Object.entries(target)) {
    const wobble = Math.sin(time * .6 + i) * (key === 'temp' ? .08 : key === 'hr' ? 2 : .5);
    result[key] = key in overrides ? overrides[key] : Math.round((value + wobble) * (key === 'temp' ? 10 : 1)) / (key === 'temp' ? 10 : 1);
  }
  return result;
}

export const monitorChannels = [
  { key: 'hr', label: 'HR / ECG', unit: 'bpm', color: 'mint', min: 0, max: 200 },
  { key: 'spo2', label: 'SpO₂ / Pleth', unit: '%', color: 'blue', min: 0, max: 100 },
  { key: 'rr', label: 'Respiratory rate', unit: '/min', color: 'mint', min: 0, max: 60 },
  { key: 'map', label: 'Blood pressure / MAP', unit: 'mmHg', color: 'blue', min: 0, max: 160 },
  { key: 'etco2', label: 'EtCO₂ / Capnogram', unit: 'mmHg', color: 'amber', min: 0, max: 80 },
  { key: 'temp', label: 'Temperature trend', unit: '°C', color: 'amber', min: 34, max: 42, step: .1 },
];

const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
export function waveSpec(key, values) {
  const amplitudes = { hr: values.hr / 90, rr: values.rr / 20, spo2: values.spo2 / 98, map: values.map / 90, etco2: values.etco2 / 38, temp: (values.temp - 34) / 4.5 };
  return { rate: Math.max(0, key === 'rr' || key === 'etco2' ? values.rr : key === 'temp' ? 3 : values.hr), amplitude: clamp(amplitudes[key], 0, 1.8) };
}

export function waveSample(key, phase) {
  const p = ((phase % 1) + 1) % 1;
  const g = (center, width) => Math.exp(-(((p-center)/width)**2));
  if (key === 'hr') return .12*g(.18,.04) - .18*g(.34,.025) + g(.4,.035) - .3*g(.46,.03) + .22*g(.65,.09);
  if (key === 'rr') return Math.sin(p*Math.PI*2) * .6;
  if (key === 'etco2') return p < .2 ? 0 : p < .3 ? (p-.2)*7 : p < .7 ? .7+(p-.3)*.18 : p < .8 ? (.8-p)*7.7 : 0;
  if (key === 'temp') return .25*Math.sin(p*Math.PI*2);
  return Math.pow(Math.sin(p*Math.PI), 4) * (.9 + .1*Math.sin(p*4*Math.PI));
}
