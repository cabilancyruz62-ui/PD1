import { ClipboardCheck, Syringe, ArrowUpRight } from 'lucide-react';

export default function ModeSelection({ connected, busy, onSelect, onRetry, withPanel }) {
  return <section className={`mode-selection ${withPanel ? 'with-panel' : ''}`} aria-label="Choose assessment mode">
    <span className="eyebrow">VETERINARY ANESTHESIA · TRAINING STATION</span><h1>Choose your assessment.</h1><p>One patient. One complication. A recorded student response.</p>
    <div className="mode-cards">
      <button disabled={!connected || busy} onClick={() => onSelect('full')}><span className="mode-icon"><Syringe size={26}/></span><small>OPTION 1</small><h2>Full procedure<br/>+ scenario</h2><p>Review the patient, assess the initial angle and confirm anesthesia injection. Then verify an RFID drug and assess its intervention injection angle.</p><span className="mode-action">Begin full assessment <ArrowUpRight size={17}/></span></button>
      <button disabled={!connected || busy} onClick={() => onSelect('direct')}><span className="mode-icon"><ClipboardCheck size={26}/></span><small>OPTION 2</small><h2>Direct scenario<br/>assessment</h2><p>Skip initial anesthesia, start one complication, verify an RFID drug, then perform the intervention injection and angle assessment.</p><span className="mode-action">Begin scenario assessment <ArrowUpRight size={17}/></span></button>
    </div>
    {!connected && <div className="backend-required" role="status"><strong>Assessment backend unavailable — mode selection is paused.</strong><p>Keep the frontend running. In a second terminal, open the backend folder and run:</p><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}> .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000</pre><p>The cards unlock automatically when the backend connects.</p><button className="secondary" onClick={onRetry}>Retry connection</button></div>}
    <p className="notice">Simulation hardware is available in both modes. Drug 1–3 and all scoring rules are placeholders for expert review.</p>
  </section>;
}
