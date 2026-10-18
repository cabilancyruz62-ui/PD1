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
