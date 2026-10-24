"""USB serial -> FastAPI adapter for the ESP32 sensing sketch (firmware v3.1).

The backend accepts structured hardware events at POST /api/hardware/events. The
ESP32 prints one JSON line every 50 ms over USB. This script reads those lines,
adds the session/stage IDs and unique event IDs the backend requires, and forwards:

  status  once per second   (connection flags)
  angle   at most --angle-hz, only while an injection stage is active
  rfid    once per physical scan (firmware scan_seq change)

Run from the backend folder, with the backend already running:
  python serial_bridge.py --port COM5
  python serial_bridge.py --list-ports
  python serial_bridge.py --file sample.jsonl      (replay a saved capture, no hardware)

Close the Arduino Serial Monitor first: only one program can open the port. Typing a
single firmware command letter (c, l, z, 1, 2, 3, x, p, f, s, r, h) plus Enter in this
terminal sends it to the ESP32.

Notes:
- Quaternions are NOT forwarded. The backend would treat them as a paired-quaternion
  measurement and reject it without a registered calibration. The firmware already
  computes a yaw-free angle relative to the forelimb, which is sent as angle_deg.
- A sample is marked calibrated only when the firmware reports angle_valid, a live
  dummy sensor, and cal_ok (needle 'c' and level 'l' both saved).
"""
import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from uuid import uuid4

COMMAND_LETTERS = set("clz123xpfsrh")


class BackendClient:
    """Minimal HTTP client; raises BackendRejected for 4xx so callers can resync."""

    def __init__(self, base_url, timeout=2.0):
        self.base_url, self.timeout = base_url.rstrip("/"), timeout

    def get_state(self):
        with urllib.request.urlopen(self.base_url + "/api/assessment/state", timeout=self.timeout) as response:
            return json.loads(response.read())

    def post_event(self, event):
        request = urllib.request.Request(self.base_url + "/api/hardware/events", data=json.dumps(event).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise BackendRejected(error.code, error.read().decode(errors="replace")) from error


class BackendRejected(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:200]}")
        self.status = status


class Bridge:
    def __init__(self, client, device_id="esp32-station-1", angle_hz=5.0, require_dummy=True, clock=time.monotonic, log=print):
        self.client, self.device_id, self.require_dummy, self.clock, self.log = client, device_id, require_dummy, clock, log
        self.angle_interval = 1.0 / angle_hz
        self.run_id = uuid4().hex[:8]       # keeps event IDs unique across bridge restarts
        self.counters = {"status": 0, "angle": 0, "rfid": 0, "error": 0}
        self.session_id = self.stage_id = None
        self.last_state_fetch = -1e9
        self.last_line_at = None
        self.last_status_at = -1e9
        self.last_angle_at = -1e9
        self.last_scan_seq = None
        self.latest = {}
        self.component_ok = {"mpu": True, "rfid": True}

    # ---- helpers
    def event(self, kind, **fields):
        self.counters[kind] += 1
        return {"type": kind, "source": "esp32", "device_id": self.device_id, "event_id": f"{self.run_id}-{kind}-{self.counters[kind]}", **fields}

    def send(self, event):
        try:
            return self.client.post_event(event)
        except BackendRejected as error:
            self.log(f"# backend rejected {event['type']}: {error}")
            self.last_state_fetch = -1e9   # IDs probably changed; resync before next sample
        except (urllib.error.URLError, OSError, ValueError) as error:
            self.log(f"# backend unreachable: {error}")
        return None

    def refresh_ids(self, force=False):
        now = self.clock()
        if not force and now - self.last_state_fetch < 0.5:
            return
        self.last_state_fetch = now
        try:
            state = self.client.get_state()
            self.session_id, self.stage_id = state.get("session_id"), state.get("injection_stage_id")
        except (urllib.error.URLError, OSError, ValueError) as error:
            self.log(f"# cannot read backend state: {error}")

    def flags(self):
        d = self.latest
        mpu = bool(d.get("syringe_ok")) and (bool(d.get("dummy_ok")) or not self.require_dummy)
        return {"esp32_connected": self.last_line_at is not None and self.clock() - self.last_line_at < 2.0, "mpu_connected": mpu, "rfid_connected": bool(d.get("rfid_ok"))}

    # ---- main entry points
    def handle_line(self, line):
        line = line.strip()
        if not line:
            return
        if line.startswith("#"):
            self.log(line)
            return
        try:
            data = json.loads(line)
        except ValueError:
            return                       # partial line after a reset; ignore
        if not isinstance(data, dict):
            return
        self.latest, self.last_line_at = data, self.clock()
        self.heartbeat()
        self.forward_rfid(data)
        self.forward_angle(data)

    def heartbeat(self):
        now = self.clock()
        if now - self.last_status_at < 1.0:
            return
        self.last_status_at = now
        flags = self.flags()
        self.send(self.event("status", **flags))
        for name, ok in (("mpu", flags["mpu_connected"]), ("rfid", flags["rfid_connected"])):
            if self.component_ok[name] and not ok:
                self.send(self.event("error", component=name, message=f"{name.upper()} not reporting valid data from the ESP32"))
            self.component_ok[name] = ok

    def forward_rfid(self, data):
        seq, uid = data.get("scan_seq"), data.get("uid")
        if not isinstance(seq, int) or isinstance(seq, bool):
            return
        if self.last_scan_seq is None or seq < self.last_scan_seq:
            self.last_scan_seq = seq     # first line, or ESP32 rebooted: do not replay old scans
            return
        if seq == self.last_scan_seq or not isinstance(uid, str) or not uid.strip():
            return
        self.last_scan_seq = seq
        self.refresh_ids(force=True)
        self.log(f"# tag scan -> backend: {uid}")
        self.send(self.event("rfid", session_id=self.session_id, uid=uid.strip()))

    def forward_angle(self, data):
        now = self.clock()
        angle = data.get("angle")
        if now - self.last_angle_at < self.angle_interval or isinstance(angle, bool) or not isinstance(angle, (int, float)):
            return
        self.refresh_ids()
        if not self.session_id or not self.stage_id:
            return                       # no injection stage is waiting for angle samples
        self.last_angle_at = now
        calibrated = bool(data.get("angle_valid") and data.get("cal_ok") and (data.get("dummy_ok") or not self.require_dummy))
        packet = {"session_id": self.session_id, "injection_stage_id": self.stage_id, "angle_deg": float(min(90.0, max(0.0, angle))), "calibrated": calibrated}
        if calibrated:
            packet["calibration_id"] = str(data.get("cal_id") or "fw-unknown")
        self.send(self.event("angle", **packet))


def read_serial(port, baud, bridge, stop):
    import serial  # pyserial, imported lazily so --file and the tests do not need it
    while not stop.is_set():
        try:
            with serial.Serial(port, baud, timeout=0.2) as ser:
                bridge.log(f"# opened {port} at {baud} baud")
                threading.Thread(target=forward_console, args=(ser, stop), daemon=True).start()
                while not stop.is_set():
                    raw = ser.readline()
                    if raw:
                        bridge.handle_line(raw.decode("utf-8", errors="replace"))
                    else:
                        bridge.heartbeat()   # keep the backend informed even if the ESP32 goes quiet
        except (serial.SerialException, OSError) as error:
            bridge.log(f"# serial error: {error}; retrying in 2 s")
            time.sleep(2)


def forward_console(ser, stop):
    while not stop.is_set():
        try:
            text = sys.stdin.readline()
        except (OSError, ValueError):
            return
        if not text:
            return
        text = text.strip()
        if len(text) == 1 and text in COMMAND_LETTERS:
            ser.write(text.encode())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--port", help="serial port, for example COM5 or /dev/ttyUSB0")
    source.add_argument("--file", help="replay JSON lines from a file ('-' for stdin) instead of a serial port")
    source.add_argument("--list-ports", action="store_true")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--device-id", default="esp32-station-1")
    parser.add_argument("--angle-hz", type=float, default=5.0, help="maximum angle events per second (default 5)")
    parser.add_argument("--allow-missing-dummy", action="store_true", help="bench testing with only the syringe MPU; angle assumes a level forelimb")
    args = parser.parse_args(argv)
    if args.list_ports:
        from serial.tools import list_ports
        for item in list_ports.comports():
            print(item.device, "-", item.description)
        return 0
    if not args.port and not args.file:
        parser.error("choose --port, --file or --list-ports")
    bridge = Bridge(BackendClient(args.url), args.device_id, args.angle_hz, not args.allow_missing_dummy)
    if args.file:
        handle = sys.stdin if args.file == "-" else open(args.file, encoding="utf-8")
        for line in handle:
            bridge.handle_line(line)
            time.sleep(0.05)
        return 0
    stop = threading.Event()
    try:
        read_serial(args.port, args.baud, bridge, stop)
    except KeyboardInterrupt:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
