import { useEffect, useRef } from 'react';
import { CircleAlert } from 'lucide-react';
import { getDrugFeedback } from '../lib/feedback';

export default function InterventionNotice({ notice, state, onDismiss, onContinue }) {
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    if (notice && !element.open) element.showModal();
    return () => { if (element?.open) element.close(); };
  }, [notice?.id]);
  if (!notice) return null;
  const success = (notice.kind === 'drug_verified' || notice.kind === 'completed' || notice.kind === 'correct');
  const incorrect = notice.kind === 'incorrect' || notice.kind === 'unregistered';
  const drugFeedback = getDrugFeedback(state);
  const message = notice.kind === 'incorrect' && drugFeedback?.status === 'wrong' ? drugFeedback.message : notice.message;
  const title = notice.kind === 'drug_verified' ? 'Drug Verified' : success ? 'Assessment Results Ready' : notice.kind === 'incorrect' ? 'Wrong drug' : notice.kind === 'unregistered' ? 'Unregistered RFID Tag' : notice.kind === 'recognition' ? 'Recognition Feedback' : 'Hardware / Scan Notice';
  return <dialog ref={dialog} className={`intervention-dialog ${success ? 'success' : ''}`} onCancel={event => { event.preventDefault(); onDismiss(); }} aria-labelledby="intervention-title"><span className="eyebrow">{notice.kind === 'completed' ? 'Assessment Complete' : 'During Feedback'}</span><h2 id="intervention-title" className="feedback-dialog-title">{notice.kind === 'incorrect' && <CircleAlert size={25} aria-hidden="true"/>}{title}</h2><p>{message}</p><dl className="detail-list"><div><dt>Detected drug</dt><dd>{notice.drug?.name || 'No registered drug'}</dd></div><div><dt>Active scenario</dt><dd>{state.catalog.scenarios[notice.scenario_id]?.name || 'No active scenario'}</dd></div><div><dt>Status</dt><dd>{notice.kind}</dd></div></dl><div className="action-row">{incorrect ? <><button className="primary" onClick={onDismiss}>Try Again</button><button className="secondary" onClick={onContinue}>Continue Assessment</button></> : <button className="primary" onClick={onContinue}>{notice.kind === 'drug_verified' ? 'Continue to Intervention' : notice.kind === 'completed' ? 'View Post Feedback' : 'Continue Assessment'}</button>}</div>{incorrect && <p className="notice">Attempts remain recorded. An incorrect choice does not change the vital-sign targets or end the scenario.</p>}</dialog>;
}
