# Frontend tracking modes

Open **Settings → Tracking mode**, at the top of the Settings panel. This selection is independent of assessment Options 1 and 2, the assigned breed, and the ESP32 input source. It is available before choosing an assessment option once the browser camera is connected. The selected mode is retained in this browser; a fresh browser starts with Normal.

| Choice | Camera overlay behavior | Setup |
| --- | --- | --- |
| Normal — manual placement | Retains the existing manual dog placement and assessment pose rules | Use Settings → 3D Patient for placement and alignment preview |
| Design 1 — ArUco marker | Locates marker 0 automatically and anchors the dog to its image-space position, width and rotation | Attach the printed `DICT_4X4_50` ID 0 card rigidly to the pad |
| Design 2 — ORB + RANSAC | Matches a manually captured reference from the pad; can reacquire that reference | Remove printed targets and helpers, then select original surface details |
| Design 3 — Optical flow | Follows manually selected surface points; requires selection again after loss or stream interruption | Remove printed targets and helpers, then select original surface details |

Designs 2 and 3 use **no added texture helper** in the planned physical-pad trials. Their integration is preliminary: the original photos failed ORB checks, and a real pad recording is still required to assess these methods. Rejected references and insufficient features are valid outcomes. The browser checks use synthetic camera fixtures to exercise the software, not to establish physical-pad accuracy.

## Run and try Design 1

Start the frontend and backend normally as described in [RUNNING.md](RUNNING.md). Restart a backend that was running before the tracking route was added. Backend requirements now include the shared tracking dependencies. If using an older environment, run from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Close the standalone OpenCV preview before using the browser so both applications do not compete for the webcam. The browser uses its selected camera; its device labels are independent of standalone OpenCV camera index 0/1.

1. Print the [ArUco-only A4 sheet](../designs/references/injection-pad/targets/print-targets.pdf) at 100% / Actual size. Check the 50 mm bar. Preserve the marker's white margin and mount it on a removable rigid tab fixed to the pad, outside the injection and sensor areas.
2. Open Settings and select **Design 1 — ArUco marker**. Show marker 0 clearly. The status should become **Target tracked**, an outline should appear, and the assigned breed's dog should appear on the target.
3. Adjust **Dog width / target width**, horizontal/vertical offsets, and rotation offset in the tracking section. These offsets follow the target's image rotation and scale. Each breed and tracking mode has separate alignment values for this page session. Under **3D Patient**, adjust the dog's viewing angle and opacity.
4. Cover the marker: the tracked outline and camera dog should disappear. Uncover it: they should return. Move the camera slowly while keeping the pad stationary to check screen alignment. Mirror camera reflects the tracked layer together with the video.
5. Select **Normal** to restore manual placement and stop tracking-frame transmission. In Normal, the dog follows existing assessment visibility rules; enable the alignment preview under 3D Patient if testing before an assessment.

Before an assessment, a tracked target shows the standing dog as an alignment preview. During an assessment, the existing standing/lying and recovery rules determine pose. Target detection does not complete an injection, choose a drug, change scoring, or modify ESP32 measurements. The rotatable breed inspector remains separate from camera tracking.

## Select the original pad for Designs 2 and 3

Select the desired mode and press **Select pad region**. A live camera selection view opens. Keep the camera and pad still, drag around details on the pad itself, and press **Use pad region**. Exclude hands, patterned background, sensors, rulers, and printed targets. Confirmation captures a fresh frame from the actual video to initialize the tracker; it does not use the old image from when the selector opened or the selection canvas containing the drawn rectangle. Subsequent frames come from the live camera.

ORB requires at least 48 pixels per selected side plus enough distributed reference features. Optical flow requires a sufficiently textured selection, with at least 12 pixels per selected side. These are software minima, not guarantees that the smooth pad will track. A featureless selection displays a rejection and leaves the dog hidden. ORB feedback includes the actual usable reference-point count and point coverage when available. Too few points and clustered points are different quality failures; neither is fixed by allowing an invalid anchor. Try a closer, sharply focused view with diffuse light and original channel/vein junctions distributed across the region. Press **Select pad region** to try again. Printed texture helpers are not used.

ORB attempts reference matching on each frame and can reacquire it after occlusion. Optical flow stays lost until manually selected again; it also needs a new selection after disconnecting or changing cameras. Camera changes invalidate old references in both modes.

## Data path and limits

The browser remains the only webcam owner. Normal sends no frames for tracking. A tracked mode samples the existing video to JPEG at up to 10 frames per second, with at most one frame in flight and a maximum image side of 640 pixels. `/api/ws/tracking` processes these in the configured backend using the same Python trackers as `designs/`; frames are held in memory and are not saved. Use the intended local backend when running this training station.

Each tracking connection owns its own tracker. OpenCV work runs outside the asynchronous API event loop so assessment and hardware connections can continue. Disconnects, camera changes, mode changes, invalid tracking results and stale frames hide the camera dog. A result older than 750 ms from capture cannot enable the tracked overlay; the freshness check updates every 100 ms. A lost result clears the outline immediately when received.

Image coordinates account for the camera video's centered `object-fit: cover`, viewport changes and mirroring. The dog follows **2D position, image scale and screen rotation**. Camera intrinsics, perspective-aware 3D pose, metric scale, and the pad-to-dog transform remain uncalibrated. A visible marker or matching surface is a proxy; it does not prove that the complete dummy is present. Built-in dog models remain in use; loading an animated Blender rig into this tracked overlay is a separate step.

## Verification

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend -p test_*.py
```

From `frontend`, run `npm.cmd test` and `npm.cmd run build`. The tests cover the real tracking WebSocket with JPEG frames, marker IDs, loss and reacquisition, independent connection state, selection rejection, flow loss behavior, stale-result gating, source/design changes and coordinate projection. Physical camera accuracy, light changes and hand occlusion still require the mounted-pad trial.

On Windows with Edge installed, run the browser integration checks from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe frontend/tests/tracking.browser.py
```

This launches isolated hidden services and a browser with synthetic camera frames and a temporary assessment database. It checks all four modes, dog visibility, loss/reacquisition, translation, mirroring, region selection, flow disconnection, featureless-region rejection and mobile layout, then stops its own processes. It does not use the physical webcam or the training station's saved assessment records.
