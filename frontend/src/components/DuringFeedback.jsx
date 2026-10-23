import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, CircleAlert, Clock3 } from 'lucide-react';
import { getAngleFeedbackPopup } from '../lib/feedback';
import InterventionNotice from './InterventionNotice';

function AngleFeedbackPopup({ feedback, onDismiss }) {
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    if (!element.open) element.showModal();
    return () => { if (element.open) element.close(); };
  }, []);
  const Icon = feedback.status === 'valid' ? CheckCircle2 : feedback.status === 'waiting' ? Clock3 : CircleAlert;
  return <dialog ref={dialog} className={`intervention-dialog during-feedback-dialog ${feedback.status === 'valid' ? 'success' : ''}`} onCancel={event => { event.preventDefault(); onDismiss(); }} aria-labelledby="during-feedback-title" aria-describedby="during-feedback-message">
    <span className="eyebrow">During Feedback</span>
    <h2 id="during-feedback-title" className="feedback-dialog-title"><Icon size={25} aria-hidden="true"/>{feedback.title}</h2>
    <p id="during-feedback-message">{feedback.message}</p>
    <div className="action-row"><button className="primary" onClick={onDismiss}>Continue</button></div>
  </dialog>;
}

export default function DuringFeedback({ state, notice, onDismissNotice, onContinueNotice, enabled = true }) {
  const feedback = getAngleFeedbackPopup(state);
  const lastSeen = useRef(null);
  const [openKey, setOpenKey] = useState(null);
  const key = feedback?.key || null;
  useEffect(() => {
    if (!key) { lastSeen.current = null; setOpenKey(null); return; }
    // Backend notices (RFID, recognition, completion) have priority so native
    // dialogs never stack. The latest angle result is shown after dismissal.
    if (!enabled || notice) return;
    if (lastSeen.current !== key) { lastSeen.current = key; setOpenKey(key); }
  }, [key, notice, enabled]);
  if (!enabled) return null;
  if (notice) return <InterventionNotice key={notice.id} notice={notice} state={state} onDismiss={onDismissNotice} onContinue={onContinueNotice}/>;
  if (!feedback || openKey !== key) return null;
  return <AngleFeedbackPopup feedback={feedback} onDismiss={() => setOpenKey(null)}/>;
}
