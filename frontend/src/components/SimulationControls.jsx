export function formatDuration(seconds) {
  return `${Math.floor(seconds/60).toString().padStart(2,'0')}:${Math.floor(seconds%60).toString().padStart(2,'0')}`;
}

export default function SimulationControls({ simulation, patient, onStart, onEnd }) {
  const running = simulation.status === 'running';
  return <div className="simulation-bar">
    <div><span className="eyebrow">STUDENT {simulation.student} · {running ? 'SIMULATION IN PROGRESS' : 'READY FOR NEXT SIMULATION'}</span><strong>{patient.Name} <small>{patient.Breed}</small></strong></div>
    <span className="session-timer" aria-label="Simulation elapsed time">{formatDuration(simulation.elapsed)}</span>
    <button className={running ? 'secondary end-simulation' : 'primary'} onClick={running ? onEnd : onStart}>{running ? 'End Simulation' : 'Start Simulation'}</button>
  </div>;
}
