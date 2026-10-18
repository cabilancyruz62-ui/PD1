"""Hardware API placeholder. Replace None with calibrated sensor measurements."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, StrictBool
from wire import WireMonitor

wire_monitor = WireMonitor()


class WireSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connected: StrictBool

app = FastAPI(title="Veterinary Anesthesia AR Backend")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/sensors")
def sensors():
    # TODO: Read the calibrated relative needle/forelimb angle and delivered fluid volume.
    # None means no physical sensor reading is available yet (do not fabricate readings).
    return {"status": "Awaiting angle/volume hardware", "angle_deg": None, "volume_ml": None, "wire": wire_monitor.snapshot()}


@app.post("/api/hardware/wire")
def update_wire(signal: WireSignal):
    """ESP32 should send the debounced input state every second, even when unchanged."""
    return {"wire": wire_monitor.update(signal.connected)}
