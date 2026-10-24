import { useRef } from 'react';
import DummyOverlay from './DummyOverlay.jsx';

// Retain the renderer across target loss, while hiding the entire layer and
// pausing its drawing. Recreating WebGL on every missed frame causes flicker.
export default function TrackedOverlay({ projection, viewport, mode, mirrored, modelVisible, breedId, pose, sessionId }) {
  const lastProjection = useRef(null);
  if (projection) lastProjection.current = projection;
  return <div className={`tracked-overlay-plane ${mirrored ? 'mirrored' : ''}`} hidden={!projection} data-tracking-mode={mode}>
    {projection && <svg className="tracking-target-outline" viewBox={`0 0 ${viewport.width} ${viewport.height}`} aria-hidden="true"><polygon points={projection.corners.map(point => point.join(',')).join(' ')}/></svg>}
    {modelVisible && lastProjection.current && <DummyOverlay key={sessionId || 'preview'} breedId={breedId}
      placement={lastProjection.current.placement} pose={pose || 'standing'} visible={Boolean(projection)}/>}
  </div>;
}
