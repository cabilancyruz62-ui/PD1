import { CheckCircle2, CircleAlert, Clock3 } from 'lucide-react';
import { getAngleFeedback, getDrugFeedback } from '../lib/feedback';

export default function DuringFeedback({ state }) {
  if (!state?.mode || ['evaluated', 'ended', 'interrupted'].includes(state.phase)) return null;
  const drug = getDrugFeedback(state), angle = getAngleFeedback(state);
  const messages = [drug && { ...drug, id: 'drug' }, angle && { ...angle, id: 'angle' }].filter(Boolean);
  return <section className="during-feedback" aria-label="During feedback">
    <h3>During Feedback</h3>
    <span className="feedback-announcement" role="status" aria-live="polite">{messages.map(item => item.id === 'drug' ? item.message : item.title).join(' ')}</span>
    {messages.length ? messages.map(item => {
      const Icon = item.status === 'valid' ? CheckCircle2 : item.status === 'waiting' ? Clock3 : CircleAlert;
      return <p className={`feedback-message feedback-${item.status}`} key={item.id}><Icon size={18} aria-hidden="true"/><span>{item.message}</span></p>;
    }) : <p className="notice">Feedback will appear here after a drug scan or during an injection.</p>}
  </section>;
}
