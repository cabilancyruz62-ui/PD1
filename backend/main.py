"""Local training-station API; camera frames are never sent here."""
import asyncio
import os
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from assessment import AssessmentService, AssessmentError
from assessment_models import AssessmentCommand, HardwareEvent, WireSignal
from assessment_store import AssessmentStore
from wire import WireMonitor

wire_monitor = WireMonitor()
store = AssessmentStore(os.environ.get("ASSESSMENT_DB_PATH", str(Path(__file__).parent / "data/assessments.sqlite3")))
config_path = os.environ.get("ASSESSMENT_CONFIG_PATH")
assessment = AssessmentService(store=store, config=json.loads(Path(config_path).read_text()) if config_path else None)
app = FastAPI(title="Veterinary Anesthesia AR Backend")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def invalid_input(request, error):
    # Do not echo invalid NaN/Infinity inputs into a JSON response.
    return JSONResponse(status_code=422, content={"detail": [{"loc": item["loc"], "msg": item["msg"], "type": item["type"]} for item in error.errors()]})


def state_payload():
    return {**assessment.snapshot(), "wire": wire_monitor.snapshot()}


@app.get("/api/health")
def health():
    return {"status": "ok", "instance_id": assessment.instance_id}


@app.get("/api/sensors")
def sensors():
    state = assessment.snapshot()
    angle = state["angle"]
    return {"status": "Simulated hardware" if state["input_source"] == "simulation" else "ESP32 hardware", "angle_deg": angle["angle_deg"] if angle and angle["fresh"] and angle["calibrated"] else None, "volume_ml": None, "wire": wire_monitor.snapshot(), "hardware": state["hardware"]}


@app.post("/api/hardware/wire")
def update_wire(signal: WireSignal):
    return {"wire": wire_monitor.update(signal.connected)}


@app.get("/api/assessment/state")
def get_state():
    return state_payload()


@app.post("/api/assessment/command")
def command(command: AssessmentCommand):
    try:
        state = assessment.command(command.model_dump(exclude_none=True))
        return {**state, "wire": wire_monitor.snapshot()}
    except AssessmentError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/hardware/events")
def hardware_event(event: HardwareEvent):
    try:
        return assessment.hardware_event(event.model_dump(exclude_none=True))
    except AssessmentError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/assessment/results")
def results():
    return {"results": store.results(), "placeholder_rubric": True}


@app.websocket("/api/ws/assessment")
async def assessment_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"type": "assessment_state", "state": state_payload()})
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=.5)
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass


@app.websocket("/api/ws/hardware")
async def hardware_socket(websocket: WebSocket):
    await websocket.accept()
    initial = assessment.snapshot()
    await websocket.send_json({"type": "ready", "session_id": initial["session_id"], "injection_stage_id": initial["injection_stage_id"], "message": "Send a status heartbeat every second. Read current session_id and injection_stage_id before angle samples."})
    try:
        while True:
            try:
                data = await websocket.receive_json()
                event = HardwareEvent.model_validate(data)
                state = assessment.hardware_event(event.model_dump(exclude_none=True))
                await websocket.send_json({"type": "accepted", "session_id": state["session_id"], "injection_stage_id": state["injection_stage_id"], "phase": state["phase"], "revision": state["revision"]})
            except (ValidationError, AssessmentError, ValueError) as error:
                await websocket.send_json({"type": "error", "message": str(error)})
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
