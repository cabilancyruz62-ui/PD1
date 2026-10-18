export const sampleVitals = [['HR','90','bpm','mint'],['SpO₂','98','%','blue'],['RR','20','/min','mint'],['BP / MAP','120/80 · 93','mmHg','blue'],['EtCO₂','38','mmHg','amber'],['Temperature','38.5','°C','amber']];

// Hardware only gates the simulated monitor; it never supplies physiological readings.
export function getVitalsState({ triggerEnabled, source, simulatedConnected, wire, now = Date.now(), receivedAt = 0 }) {
  if (!triggerEnabled) return { active: true, message: 'Wire trigger off · connection not required' };
  if (source === 'simulation') return {
    active: simulatedConnected,
    message: simulatedConnected ? 'Simulated wire connected' : 'Waiting for simulated wire connection',
  };
  const fresh = wire?.source === 'esp32' && wire.fresh === true && receivedAt > 0 && now - receivedAt < 3000;
  if (!fresh) return { active: false, message: 'Waiting for a fresh ESP32 wire signal' };
  return { active: wire.connected === true, message: wire.connected === true ? 'ESP32 wire connected' : 'ESP32 wire disconnected · monitor paused' };
}
