import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision';

let tracker;
self.onmessage = async ({ data }) => {
  if (data.initialize) {
    try {
      const files = await FilesetResolver.forVisionTasks(`https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${__MEDIAPIPE_VERSION__}/wasm`);
      tracker = await HandLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task', delegate: 'CPU' },
        runningMode: 'VIDEO', numHands: 2,
      });
      self.postMessage({ ready: true });
    } catch (error) { self.postMessage({ error: `Hand tracking could not load. Internet access is required. ${error.message}` }); }
    return;
  }
  const { bitmap, timestamp } = data;
  try {
    const result = tracker.detectForVideo(bitmap, timestamp);
    self.postMessage({ landmarks: result.landmarks, width: bitmap.width, height: bitmap.height });
  } catch (error) { self.postMessage({ error: `Hand tracking failed: ${error.message}` }); }
  finally { bitmap.close(); }
};
