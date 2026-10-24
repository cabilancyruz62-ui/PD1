"""Optional isolated production-browser measurements, never physical sensor timings.

Importing this module does not start services. ``run_runtime`` explicitly starts
a private FastAPI instance, Vite preview, and a temporary headless Edge profile.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen


MODES = ("aruco", "orb", "optical-flow")
MB = 1_000_000


def percentile(values, percent):
    """Linear interpolation between sorted observations, including endpoints."""
    if not 0 <= percent <= 100:
        raise ValueError("Percentile must be between 0 and 100")
    numbers = sorted(float(value) for value in values)
    if not numbers or any(not math.isfinite(value) for value in numbers):
        raise ValueError("Percentiles require finite observations")
    position = (len(numbers) - 1) * percent / 100
    lower, upper = math.floor(position), math.ceil(position)
    return numbers[lower] + (numbers[upper] - numbers[lower]) * (position - lower)


def summarize_latency(observations):
    """Keep failures in the denominator; never replace them with zero latency."""
    good = []
    for item in observations:
        elapsed = item.get("elapsed_ms")
        if item.get("status") == "measured":
            if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError("Measured latency must be a finite nonnegative number")
            good.append(float(elapsed))
    return {
        "unit": "ms", "attempted_samples": len(observations),
        "successful_samples": len(good), "failed_samples": len(observations) - len(good),
        "mean_ms": statistics.mean(good) if good else None,
        "p50_ms": percentile(good, 50) if good else None,
        "p95_ms": percentile(good, 95) if good else None,
        "observations": observations,
    }


def process_tree_rss(roots, psutil_module):
    """Sum each PID once across owned process trees, recording vanished roots.

    RSS is resident/working-set memory. Shared pages can appear in multiple
    processes, so this is an operational RSS sum, not unique physical memory.
    """
    seen = set()
    groups = {}
    missing_roots, vanished_children = [], []
    errors = (psutil_module.NoSuchProcess, psutil_module.AccessDenied)
    for label, pid in roots.items():
        try:
            root = psutil_module.Process(pid)
            members = [root, *root.children(recursive=True)]
        except errors:
            missing_roots.append(label)
            continue
        rss = 0
        pids = []
        for process in members:
            if process.pid in seen:
                continue
            seen.add(process.pid)
            try:
                rss += process.memory_info().rss
                pids.append(process.pid)
            except errors:
                vanished_children.append(process.pid)
                if process.pid == pid:
                    missing_roots.append(label)
        groups[label] = {"rss_bytes": rss, "process_count": len(pids), "pids": pids}
    valid = not missing_roots and set(groups) == set(roots)
    return {"valid": valid, "rss_bytes": sum(item["rss_bytes"] for item in groups.values()) if valid else None,
            "components": groups, "missing_roots": missing_roots, "vanished_children": vanished_children}


def summarize_memory(observations):
    valid = [item for item in observations if item.get("valid") and item.get("rss_bytes") is not None]
    for item in valid:
        if isinstance(item["rss_bytes"], bool) or not isinstance(item["rss_bytes"], (int, float)) or item["rss_bytes"] < 0 or not math.isfinite(item["rss_bytes"]):
            raise ValueError("Memory observations require finite nonnegative bytes")
    names = sorted({name for item in valid for name in item["components"]})
    return {
        "unit": "MB", "bytes_per_mb": MB, "statistic": "sum of process-tree RSS / working sets",
        "shared_page_caveat": "Shared pages may be counted in more than one process; this is not unique physical RAM. Sampled peaks can miss shorter allocation spikes.",
        "attempted_samples": len(observations), "successful_samples": len(valid),
        "failed_samples": len(observations) - len(valid),
        "mean_mb": statistics.mean(item["rss_bytes"] for item in valid) / MB if valid else None,
        "sampled_peak_mb": max(item["rss_bytes"] for item in valid) / MB if valid else None,
        "components": {name: {
            "mean_mb": statistics.mean(item["components"][name]["rss_bytes"] for item in valid if name in item["components"]) / MB,
            "sampled_peak_mb": max(item["components"][name]["rss_bytes"] for item in valid if name in item["components"]) / MB,
        } for name in names},
        "observations": observations,
    }


def summarize_cpu(observations):
    """Summarize sampled application CPU load without turning failures into zero.

    Each observation expresses user + system CPU time as a percentage of the
    whole computer's logical CPU capacity. The mean is weighted by wall time;
    P95 and peak describe the sampled interval percentages.
    """
    valid = [item for item in observations if item.get("valid")]
    for item in valid:
        for name in ("normalized_pct", "interval_seconds", "cpu_seconds"):
            value = item.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("CPU observations require finite nonnegative " + name)
        if item["interval_seconds"] <= 0 or item["normalized_pct"] > 100:
            raise ValueError("CPU intervals must be positive and utilization between 0 and 100")
        count = item.get("logical_cpu_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("CPU observations require a positive logical CPU count")
        expected = item["cpu_seconds"] / item["interval_seconds"] / count * 100
        if not math.isclose(expected, item["normalized_pct"], rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError("CPU percentage does not match CPU time / wall time / logical CPUs")
    wall = sum(item["interval_seconds"] for item in valid)
    counts = sorted({item["logical_cpu_count"] for item in valid})
    return {
        "unit": "%", "statistic": "process-tree user + system CPU time / interval wall time / logical CPU count * 100",
        "normalization": "100% means all logical CPU capacity; one fully busy logical CPU is 100 / logical_cpu_count percent",
        "mean_statistic": "interval-duration-weighted mean of normalized CPU percentages",
        "p95_statistic": "P95 of sampled interval percentages (linear interpolation)",
        "attempted_samples": len(observations), "successful_samples": len(valid),
        "failed_samples": len(observations) - len(valid),
        "mean_pct": sum(item["normalized_pct"] * item["interval_seconds"] for item in valid) / wall if valid else None,
        "p95_pct": percentile([item["normalized_pct"] for item in valid], 95) if valid else None,
        "sampled_peak_pct": max(item["normalized_pct"] for item in valid) if valid else None,
        "cpu_seconds": sum(item["cpu_seconds"] for item in valid) if valid else None,
        "wall_seconds": wall if valid else None,
        "logical_cpu_count": counts[0] if len(counts) == 1 else None,
        "logical_cpu_counts": counts,
        "process_lifetime_caveat": "New processes are baselined at first sighting; CPU consumed before that sighting or after the last sighting of an exited process is not recoverable. Short-lived processes entirely between samples can be missed.",
        "graphics_caveat": "This headless benchmark uses SwiftShader software rendering, so browser CPU includes software graphics work; remeasure with the final GPU configuration or Electron package.",
        "observations": observations,
    }


class ProcessTreeCpuSampler:
    """Nonblocking cumulative-CPU sampler for only the owned process trees.

    ``prime`` takes a baseline before the measured window. PID + creation time
    prevents PID reuse from assigning an old process's lifetime to its successor.
    Owned roots must retain their identity; a vanished/reused root is unknown.
    """

    def __init__(self, roots, psutil_module, clock=None):
        self.roots = dict(roots)
        self.psutil = psutil_module
        self.clock = clock or time.monotonic
        self._previous = None
        self._previous_time = None
        self._root_identities = {}
        count = psutil_module.cpu_count(logical=True)
        self.logical_cpu_count = count if isinstance(count, int) and not isinstance(count, bool) and count > 0 else None

    def _snapshot(self):
        records, seen, errors = {}, {}, []
        process_errors = (self.psutil.NoSuchProcess, self.psutil.AccessDenied)
        for label, pid in self.roots.items():
            try:
                root = self.psutil.Process(pid)
                created = root.create_time()
                if isinstance(created, bool) or not isinstance(created, (int, float)) or not math.isfinite(created):
                    raise ValueError("Invalid process creation time")
                identity = (pid, created)
                expected = self._root_identities.setdefault(label, identity)
                if identity != expected:
                    errors.append({"group": label, "pid": pid, "reason": "owned root PID was reused"})
                    continue
                members = [root, *root.children(recursive=True)]
            except (*process_errors, ValueError) as error:
                errors.append({"group": label, "pid": pid, "reason": "owned root unavailable: " + str(error)})
                continue
            for process in members:
                try:
                    created = process.create_time()
                    if isinstance(created, bool) or not isinstance(created, (int, float)) or not math.isfinite(created):
                        raise ValueError("Invalid process creation time")
                    identity = (process.pid, created)
                    if process.pid in seen:
                        if seen[process.pid] != identity:
                            errors.append({"group": label, "pid": process.pid, "reason": "PID identity changed during snapshot"})
                        continue
                    seen[process.pid] = identity
                    times = process.cpu_times()
                    values = (times.user, times.system)
                    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in values):
                        raise ValueError("Invalid user/system CPU times")
                    records[identity] = {"pid": process.pid, "created": created, "group": label, "cpu_seconds": sum(values)}
                except (*process_errors, ValueError) as error:
                    errors.append({"group": label, "pid": process.pid, "reason": "process CPU unavailable: " + str(error)})
        return {"valid": not errors, "records": records, "errors": errors}

    def prime(self):
        self._previous = self._snapshot()
        self._previous_time = self.clock()

    def sample(self):
        current = self._snapshot()
        now = self.clock()
        previous, previous_time = self._previous, self._previous_time
        self._previous, self._previous_time = current, now
        interval = now - previous_time if previous_time is not None else None
        observation = {"valid": False, "normalized_pct": None, "interval_seconds": interval,
                       "cpu_seconds": None, "logical_cpu_count": self.logical_cpu_count,
                       "components": {}, "process_errors": current["errors"]}
        if previous is None:
            observation["reason"] = "No primed CPU baseline; this sample establishes the baseline"
            return observation
        if not self.logical_cpu_count:
            observation["reason"] = "Logical CPU count unavailable; capacity cannot be normalized"
            return observation
        if not current["valid"] or not previous["valid"]:
            observation["reason"] = "Current or previous process CPU snapshot incomplete; utilization is unknown"
            return observation
        if not isinstance(interval, (int, float)) or not math.isfinite(interval) or interval <= 0:
            observation["reason"] = "CPU sampling interval must be positive and finite"
            return observation
        before, after = previous["records"], current["records"]
        observation["new_processes"] = [{"pid": record["pid"], "create_time": record["created"]} for identity, record in after.items() if identity not in before]
        observation["disappeared_processes"] = [{"pid": record["pid"], "create_time": record["created"]} for identity, record in before.items() if identity not in after]
        components = {label: {"cpu_seconds": 0.0, "normalized_pct": 0.0, "process_count": 0, "pids": []} for label in self.roots}
        total = 0.0
        for identity, record in after.items():
            if identity not in before:
                continue  # First sighting is a baseline, never full lifetime CPU.
            delta = record["cpu_seconds"] - before[identity]["cpu_seconds"]
            if not math.isfinite(delta) or delta < 0:
                observation["reason"] = "Cumulative process CPU time decreased; utilization is unknown"
                return observation
            total += delta
            group = components[record["group"]]
            group["cpu_seconds"] += delta
            group["process_count"] += 1
            group["pids"].append(record["pid"])
        normalized = total / interval / self.logical_cpu_count * 100
        if not math.isfinite(normalized) or normalized > 100 + 1e-9:
            observation["reason"] = "Sampled CPU delta exceeds total logical CPU capacity; utilization is unknown"
            return observation
        for component in components.values():
            component["normalized_pct"] = component["cpu_seconds"] / interval / self.logical_cpu_count * 100
        observation.update(valid=True, cpu_seconds=total, normalized_pct=min(100.0, normalized), components=components)
        return observation


class _CDP:
    def __init__(self, connection):
        self.connection, self.sequence = connection, 0

    def call(self, method, params=None):
        self.sequence += 1
        self.connection.send(json.dumps({"id": self.sequence, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.connection.recv(timeout=20))
            if message.get("id") == self.sequence:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in result:
            raise RuntimeError(str(result["exceptionDetails"]))
        return result.get("result", {}).get("value")

    def wait(self, expression, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.evaluate(expression):
                return
            time.sleep(.1)
        body = self.evaluate("document.body.innerText.slice(-1200)")
        raise TimeoutError(f"Browser condition timed out: {expression}\n{body}")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_http(url):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=.5):
                return
        except OSError:
            time.sleep(.1)
    raise TimeoutError("Isolated service did not start: " + url)


def _wait_debug_port(profile, browser, timeout=25):
    """Wait for Edge's complete port file, including transient Windows locks.

    Edge can create DevToolsActivePort before it releases its write handle or
    finishes the second line. File existence alone does not mean it is ready.
    """
    deadline = time.monotonic() + timeout
    last_error = "port file not ready"
    path = Path(profile) / "DevToolsActivePort"
    while time.monotonic() < deadline:
        code = browser.poll()
        if code is not None:
            raise TimeoutError(f"Isolated Edge exited before debugger startup (exit {code})")
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) >= 2 and lines[0].isdecimal() and 0 < int(lines[0]) <= 65535 and lines[1].startswith("/devtools/browser/"):
                return int(lines[0])
            last_error = "port file is empty or incomplete"
        except (OSError, UnicodeError) as error:
            last_error = str(error)
        time.sleep(.1)
    raise TimeoutError("Isolated Edge debugger did not become ready: " + last_error)


def _stop(process, psutil_module):
    """Stop only processes owned by this run, including their descendants."""
    if process is None:
        return
    try:
        children = psutil_module.Process(process.pid).children(recursive=True)
    except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
        children = []
    for child in reversed(children):
        try:
            child.terminate()
        except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
            pass
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    _, alive = psutil_module.wait_procs(children, timeout=2)
    for child in alive:
        try:
            child.kill()
        except (psutil_module.NoSuchProcess, psutil_module.AccessDenied):
            pass


def _edge_path():
    candidates = [shutil.which("msedge"),
                  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
                  "C:/Program Files/Microsoft/Edge/Application/msedge.exe"]
    return next((Path(path) for path in candidates if path and Path(path).is_file()), None)


def _camera_script(marker_url, texture_url, mode):
    # Isolated synthetic artwork is deliberately labelled helper-assisted. It
    # does not establish that the smooth physical injection pad can be tracked.
    return r'''(() => {
      localStorage.setItem('pupvitals.trackingMode', MODE);
      const urls=SOURCES;
      const images=Promise.all(urls.map(url=>new Promise(resolve=>{const i=new Image();i.onload=()=>resolve(i);i.src=url;})));
      const canvas=document.createElement('canvas');canvas.width=1280;canvas.height=720;
      const context=canvas.getContext('2d');let pictures=[];
      function draw(){context.fillStyle='#858d85';context.fillRect(0,0,1280,720);
        if(MODE==='aruco'){if(pictures[0])context.drawImage(pictures[0],800,240,240,240);}
        else if(pictures[1])context.drawImage(pictures[1],720,180,480,360);}
      const loaded=images.then(v=>{pictures=v;draw();});setInterval(draw,50);
      navigator.mediaDevices.getUserMedia=async()=>{await loaded;const stream=canvas.captureStream(12);
        const track=stream.getVideoTracks()[0], settings=track.getSettings.bind(track);
        track.getSettings=()=>({...settings(),deviceId:'constraintv2-synthetic-camera'});return stream;};
      navigator.mediaDevices.enumerateDevices=async()=>[{kind:'videoinput',deviceId:'constraintv2-synthetic-camera',label:'Synthetic constraint camera',groupId:'constraintv2'}];
      window.__v2Requests=[];window.__v2Tracking={frames:0,results:0,tracked:0,lastStatus:null};
      const NativeSocket=window.WebSocket;
      window.WebSocket=class extends NativeSocket {
        constructor(url,...args){super(url,...args);this.tracking=String(url).includes('/api/ws/tracking');
          if(this.tracking)this.addEventListener('message',event=>{try{const r=JSON.parse(event.data);
            if(r.type==='tracking_result'){window.__v2Tracking.results++;window.__v2Tracking.lastStatus=r.status;if(r.status==='tracking')window.__v2Tracking.tracked++;}}catch{}});}
        send(data){if(this.tracking && data instanceof Blob)window.__v2Tracking.frames++;super.send(data);}
      };
      const nativeFetch=window.fetch.bind(window);
      window.fetch=(input,options)=>{
        let body;try{body=JSON.parse(options?.body);}catch{}
        let record;
        if(String(input).endsWith('/api/assessment/command')&&body?.action==='simulate_angle'){
          record={angle:body.angle_deg,started:performance.now(),ok:null};window.__v2Requests.push(record);}
        return nativeFetch(input,options).then(response=>{if(record){record.ok=response.ok;record.status=response.status;}return response;},error=>{if(record)record.error=String(error);throw error;});
      };
    })();'''.replace("SOURCES", json.dumps([marker_url, texture_url])).replace("MODE", json.dumps(mode))


def _select_region(cdp):
    cdp.evaluate("document.getElementById('tracking-select-region').click()")
    cdp.wait("document.querySelector('.tracking-selection-screen canvas')!==null")
    time.sleep(.2)
    rect = cdp.evaluate("(() => {const r=document.querySelector('.tracking-selection-screen canvas').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};})()")
    x0, y0 = rect["x"] + rect["w"] * 372 / 640, rect["y"] + rect["h"] * 100 / 360
    x1, y1 = rect["x"] + rect["w"] * 588 / 640, rect["y"] + rect["h"] * 260 / 360
    cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x0, "y": y0, "button": "left", "buttons": 1, "clickCount": 1})
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x1, "y": y1, "button": "left", "buttons": 1})
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x1, "y": y1, "button": "left", "buttons": 0, "clickCount": 1})
    cdp.wait("!document.querySelector('.tracking-selection-card .primary').disabled")
    cdp.evaluate("document.querySelector('.tracking-selection-card .primary').click()")


def _prepare_assessment(cdp):
    return cdp.evaluate(r'''(async()=>{
      let state=await fetch('/api/assessment/state').then(r=>r.json());
      async function command(action,fields={}){
        const response=await fetch('/api/assessment/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,session_id:state.session_id,injection_stage_id:state.injection_stage_id,...fields})});
        if(!response.ok)throw Error('Assessment setup rejected: '+await response.text());state=await response.json();
      }
      await command('select_mode',{mode:'full'});await command('configure',{input_source:'simulation',scenario_id:'hypoventilation'});
      await command('review');await command('begin_injection');
      return {patient_id:state.patient_id,phase:state.phase,source:state.input_source,angle_min:state.catalog.angle_min_deg,angle_max:state.catalog.angle_max_deg};
    })()''')


def _latency_trial(cdp, kind, expected):
    expression = r'''(async()=>{
      const kind=KIND, expected=EXPECTED;
      // Dismiss the actual modal through its public button before using controls.
      const dialog=document.querySelector('dialog[open]');
      if(dialog){const button=[...dialog.querySelectorAll('button')].find(b=>b.textContent.trim()==='Continue');if(!button)return {status:'failed',error:'Open dialog has no Continue button'};button.click();await new Promise(requestAnimationFrame);}
      const button=[...document.querySelectorAll('.demo-controls button')].find(b=>b.textContent.startsWith(kind+' angle'));
      if(!button||button.disabled)return {status:'failed',error:'Simulated-angle UI control unavailable'};
      if(document.querySelector('dialog[open]'))return {status:'failed',error:'Modal still blocks angle controls'};
      button.scrollIntoView({block:'center'});await new Promise(requestAnimationFrame);
      const value=expected.toFixed(1), title='Angle too '+kind.toLowerCase();
      const exact=()=>{const number=document.querySelector('.injection-angle .angle-number');const popup=document.querySelector('dialog[open]');
        return number && parseFloat(number.textContent)===expected && popup && popup.querySelector('#during-feedback-title')?.textContent.includes(title)
          && popup.querySelector('#during-feedback-message')?.textContent.includes(value);};
      if(exact())return {status:'failed',error:'Matching old display would invalidate this latency trial'};
      const requestIndex=window.__v2Requests.length, start=performance.now();
      return await new Promise(resolve=>{
        let finished=false,scheduled=false;
        const done=result=>{if(finished)return;finished=true;observer.disconnect();clearTimeout(timeout);resolve({...result,input_angle_deg:expected,kind});};
        const check=()=>{
          const request=window.__v2Requests[requestIndex];
          if(request?.error||request?.ok===false)return done({status:'failed',error:request.error||'HTTP '+request.status});
          if(exact()&&request?.ok===true&&!scheduled){scheduled=true;requestAnimationFrame(()=>requestAnimationFrame(()=>{
            if(exact())done({status:'measured',elapsed_ms:performance.now()-start,command_action:'simulate_angle',observed_angle_deg:parseFloat(document.querySelector('.injection-angle .angle-number').textContent),http_status:request.status});
            else scheduled=false;
          }));}
        };
        const observer=new MutationObserver(check);observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true});
        const timeout=setTimeout(()=>done({status:'failed',error:'No corresponding visible angle feedback within 5 seconds'}),5000);
        button.click();check();
      });
    })()'''.replace("KIND", json.dumps(kind)).replace("EXPECTED", json.dumps(expected))
    return cdp.evaluate(expression)


def run_runtime(project_root, *, seconds=5, samples=5, modes=MODES):
    """Measure the production website using explicit, isolated synthetic trials.

    Requires an already built ``frontend/dist`` and installed backend/OpenCV,
    psutil, websockets, Node/Vite and Edge. No dependencies are installed here.
    Startup, reference selection and a two-second warmup are excluded. Memory
    and CPU cover at least ``seconds`` plus all latency trials if those take
    longer. CPU is normalized to the whole machine's logical CPU capacity.
    """
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= 3600:
        raise ValueError("seconds must be finite and between 0 and 3600")
    if isinstance(samples, bool) or not isinstance(samples, int) or not 1 <= samples <= 1000:
        raise ValueError("samples must be an integer between 1 and 1000")
    modes = tuple(modes)
    if not modes or len(set(modes)) != len(modes) or any(mode not in MODES for mode in modes):
        raise ValueError("Choose distinct supported tracking modes")
    root = Path(project_root).resolve()
    report = {
        "status": "unmeasured", "workload": "headless synthetic browser; simulated-angle UI controls; helper-assisted tracking artwork",
        "build": "production frontend/dist served by Vite preview", "modes": [],
        "method": {
            "latency_start": "performance.now immediately before clicking the actual Low/High simulated-angle UI button",
            "latency_end": "matching fresh numeric angle and visible feedback modal after React DOM commit and two requestAnimationFrame callbacks",
            "latency_excludes": ["USB/serial/ESP32/MPU6050 transport", "physical sensor acquisition", "physical pixel scanout"],
            "memory_includes": ["owned Edge process tree", "owned Python backend process tree"],
            "memory_excludes": ["Vite static preview server", "measurement Python process", "other browser profiles", "operating system"],
            "cpu_includes": ["owned Edge process tree (including SwiftShader software rendering)", "owned Python backend process tree"],
            "cpu_excludes": ["Vite static preview server", "measurement Python process", "other browser profiles", "operating system"],
            "cpu_method": "Nonblocking differences of cumulative process user + system CPU seconds; normalize by elapsed wall seconds and logical CPU count; time-weighted mean",
            "cpu_window": "Baseline immediately before the RAM/latency window; approximately 100 ms intervals and final snapshot after the window; startup and warmup excluded",
            "cpu_process_lifetime_caveat": "New children start at first sighting; CPU before first sighting or after last sighting of an exited process, and processes entirely between samples, can be missed",
            "sample_interval_seconds": .1, "warmup_seconds": 2,
            "requested_seconds": seconds, "requested_latency_samples_per_mode": samples,
            "graphics": "headless Edge with explicit SwiftShader software rendering; not final hardware GPU or Electron measurements",
            "comparison_limit": "Synthetic markers and non-coded texture do not validate unchanged-pad tracking or physical sensor latency. Mode order is sequential, not randomized.",
            "process_isolation": "Fresh seeded Python backend and fresh temporary Edge profile per mode; private SQLite records; same production build, patient, injection stage, 1440x900 viewport and 1280x720 synthetic camera at 12 fps",
        },
    }
    try:
        import cv2
        import numpy as np
        import psutil
        from websockets.sync.client import connect
    except ImportError as error:
        return {**report, "error": "Missing runtime measurement dependency: " + str(error)}
    edge = _edge_path()
    node = shutil.which("node") or shutil.which("node.exe")
    vite = root / "frontend/node_modules/vite/bin/vite.js"
    python = root / ("backend/.venv/Scripts/python.exe" if os.name == "nt" else "backend/.venv/bin/python")
    missing = [str(path) for path in (root / "frontend/dist/index.html", vite, python) if not path.is_file()]
    if not edge or not node or missing:
        return {**report, "error": f"Runtime prerequisites unavailable: Edge={bool(edge)}, Node={bool(node)}, missing={missing}"}
    original_path = list(sys.path)
    try:
        # Trackers share designs/tracking_common.py. Keep its import path local
        # to loading, while giving run.py a unique name to avoid runner clashes.
        sys.path.insert(0, str(root / "designs"))
        spec = importlib.util.spec_from_file_location("constraintv2_design_loader", root / "designs/run.py")
        loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader)
        marker = loader.load_design("aruco").generate_marker(0)
    finally:
        sys.path[:] = original_path
    rng = np.random.default_rng(71)
    texture = cv2.GaussianBlur(rng.integers(0, 256, (240, 320, 3), np.uint8), (3, 3), 0)
    urls = []
    for image in (marker, texture):
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("Could not encode synthetic camera target")
        urls.append("data:image/png;base64," + base64.b64encode(encoded).decode("ascii"))
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryDirectory(prefix="pupvitals-constraintv2-", ignore_cleanup_errors=True) as directory:
        temporary = Path(directory).resolve()
        if temporary.parent != Path(tempfile.gettempdir()).resolve():
            raise RuntimeError("Unexpected temporary workspace")
        backend_port, frontend_port = _free_port(), _free_port()
        config = temporary / "vite.config.mjs"
        config.write_text("export default " + json.dumps({"root": str(root / "frontend"), "preview": {"proxy": {"/api": {"target": f"http://127.0.0.1:{backend_port}", "ws": True}}}}) + ";", encoding="utf-8")
        preview = None
        with (temporary / "preview.log").open("w", encoding="utf-8") as preview_log:
            try:
                preview = subprocess.Popen([node, str(vite), "preview", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort", "--config", str(config)], cwd=root / "frontend", stdout=preview_log, stderr=subprocess.STDOUT, creationflags=flags)
                _wait_http(f"http://127.0.0.1:{frontend_port}")
                for mode in modes:
                    print(f"Runtime measurement: starting {mode}", flush=True)
                    item = {"mode": mode, "status": "unmeasured", "target_condition": "printed-marker artwork" if mode == "aruco" else "synthetic non-coded texture artwork (helper-assisted; not original pad)"}
                    if mode == "normal":
                        item["target_condition"] = "no tracker; same synthetic camera containing non-coded texture artwork"
                    report["modes"].append(item)
                    browser, backend, stop_sampling, sampler = None, None, threading.Event(), None
                    memory_observations, cpu_observations = [], []
                    cpu_sampler, cpu_started, cpu_ended = None, None, None
                    with (temporary / f"backend-{mode}.log").open("w", encoding="utf-8") as backend_log:
                        try:
                            launcher = "import random,sys; random.seed(71); sys.path.insert(0," + repr(str(root / "backend")) + "); import uvicorn; uvicorn.run('main:app',host='127.0.0.1',port=" + str(backend_port) + ",ws='websockets-sansio',log_level='warning')"
                            backend = subprocess.Popen([str(python), "-c", launcher], env={**os.environ, "ASSESSMENT_DB_PATH": str(temporary / f"{mode}.sqlite3")}, stdout=backend_log, stderr=subprocess.STDOUT, creationflags=flags)
                            _wait_http(f"http://127.0.0.1:{backend_port}/api/health")
                            profile = temporary / f"edge-{mode}"
                            browser = subprocess.Popen([str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-background-networking", "--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
                            port = _wait_debug_port(profile, browser)
                            with urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as response:
                                page = next(value for value in json.load(response) if value["type"] == "page")
                            with connect(page["webSocketDebuggerUrl"], open_timeout=5) as connection:
                                cdp = _CDP(connection)
                                cdp.call("Page.enable")
                                cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
                                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": _camera_script(urls[0], urls[1], mode)})
                                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{frontend_port}"})
                                cdp.wait("document.querySelector('.app.is-live')!==null")
                                item["assessment"] = _prepare_assessment(cdp)
                                cdp.wait("document.querySelector('.injection-angle')!==null")
                                if mode != "normal":
                                    cdp.evaluate("[...document.querySelectorAll('nav button')].find(b=>b.textContent.trim()==='Settings').click()")
                                    cdp.wait("document.querySelector('.tracking-settings select')!==null")
                                    if mode in ("orb", "optical-flow"):
                                        cdp.wait("document.querySelector('.tracking-state').textContent.includes('Select pad region')")
                                        _select_region(cdp)
                                    cdp.wait("document.querySelector('.tracking-state.is-tracked')!==null", 20)
                                cdp.evaluate("[...document.querySelectorAll('nav button')].find(b=>b.textContent.trim()==='Hardware').click()")
                                cdp.wait("document.querySelector('.demo-controls button:not(:disabled)')!==null && document.querySelector('.dummy-overlay canvas')!==null")
                                item["webgl"] = cdp.evaluate("(() => {const g=document.createElement('canvas').getContext('webgl');if(!g)return {available:false};const e=g.getExtension('WEBGL_debug_renderer_info');const result={available:true,renderer:e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER),vendor:e?g.getParameter(e.UNMASKED_VENDOR_WEBGL):g.getParameter(g.VENDOR)};g.getExtension('WEBGL_lose_context')?.loseContext();return result;})()")
                                time.sleep(2)
                                roots = {"browser": browser.pid, "backend": backend.pid}
                                try:
                                    cpu_sampler = ProcessTreeCpuSampler(roots, psutil)
                                    cpu_sampler.prime()
                                    cpu_started = cpu_sampler._previous_time
                                except Exception as error:
                                    cpu_sampler = None
                                    cpu_observations.append({"valid": False, "normalized_pct": None, "interval_seconds": None, "cpu_seconds": None, "logical_cpu_count": None, "components": {}, "reason": "CPU baseline unavailable: " + str(error)})
                                started = time.monotonic()
                                def sample_cpu():
                                    nonlocal cpu_ended
                                    if cpu_sampler is None:
                                        return
                                    try:
                                        observation = cpu_sampler.sample()
                                    except Exception as error:
                                        observation = {"valid": False, "normalized_pct": None, "interval_seconds": None, "cpu_seconds": None, "logical_cpu_count": cpu_sampler.logical_cpu_count, "components": {}, "reason": "CPU sampling unavailable: " + str(error)}
                                    cpu_ended = time.monotonic()
                                    observation["elapsed_seconds"] = cpu_ended - started
                                    cpu_observations.append(observation)
                                def sample_memory():
                                    first = True
                                    while not stop_sampling.is_set():
                                        try:
                                            observation = process_tree_rss(roots, psutil)
                                        except Exception as error:
                                            observation = {"valid": False, "rss_bytes": None, "components": {}, "error": str(error)}
                                        observation["elapsed_seconds"] = time.monotonic() - started
                                        memory_observations.append(observation)
                                        # Avoid a nearly zero CPU interval on the first
                                        # immediate RAM sample; baseline was just taken.
                                        if not first:
                                            sample_cpu()
                                        first = False
                                        stop_sampling.wait(.1)
                                sampler = threading.Thread(target=sample_memory, daemon=True)
                                sampler.start()
                                before = cdp.evaluate("({...window.__v2Tracking})")
                                latency = []
                                for index in range(samples):
                                    kind = "Low" if index % 2 == 0 else "High"
                                    value = max(0, item["assessment"]["angle_min"] - 5) if kind == "Low" else min(90, item["assessment"]["angle_max"] + 15)
                                    try:
                                        observation = _latency_trial(cdp, kind, value)
                                        if not isinstance(observation, dict):
                                            raise RuntimeError("Latency trial returned no result")
                                    except Exception as error:
                                        observation = {"status": "failed", "error": str(error), "input_angle_deg": value}
                                    latency.append(observation)
                                    time.sleep(.1)
                                while time.monotonic() - started < seconds:
                                    time.sleep(max(0, min(.1, seconds - (time.monotonic() - started))))
                                stop_sampling.set()
                                sampler.join(timeout=5)
                                if not sampler.is_alive():
                                    sample_cpu()
                                item["measured_seconds"] = time.monotonic() - started
                                after = cdp.evaluate("({...window.__v2Tracking})")
                                item["tracking_diagnostics"] = {"frames_sent": after["frames"] - before["frames"], "results_received": after["results"] - before["results"], "tracked_results": after["tracked"] - before["tracked"], "last_status": after["lastStatus"], "not_an_accuracy_measurement": True}
                                item["memory"] = summarize_memory(memory_observations)
                                item["cpu"] = summarize_cpu(cpu_observations)
                                item["cpu"]["window_seconds"] = cpu_ended - cpu_started if cpu_started is not None and cpu_ended is not None else None
                                item["cpu"]["status"] = "measured" if item["cpu"]["successful_samples"] and not item["cpu"]["failed_samples"] else "partial" if item["cpu"]["successful_samples"] else "unmeasured"
                                item["latency"] = summarize_latency(latency)
                                tracking_active = mode == "normal" or (item["tracking_diagnostics"]["results_received"] > 0 and item["tracking_diagnostics"]["tracked_results"] == item["tracking_diagnostics"]["results_received"] and after["lastStatus"] == "tracking")
                                if not tracking_active:
                                    item["tracking_warning"] = "Not every received tracking result reported tracking during the observed workload; do not compare this as a continuously tracked simulation. This status check is not an accuracy measurement."
                                item["status"] = "measured" if item["memory"]["successful_samples"] and not item["memory"]["failed_samples"] and item["latency"]["successful_samples"] == samples and item["cpu"]["status"] == "measured" and tracking_active else "partial"
                        except Exception as error:
                            item["error"] = str(error)
                            item["status"] = "partial" if memory_observations else "unmeasured"
                            if memory_observations:
                                item["memory"] = summarize_memory(memory_observations)
                            backend_log.flush()
                            item["backend_log_tail"] = (temporary / f"backend-{mode}.log").read_text(encoding="utf-8", errors="replace")[-1500:]
                        finally:
                            stop_sampling.set()
                            if sampler:
                                sampler.join(timeout=5)
                            if "cpu" not in item:
                                item["cpu"] = summarize_cpu(cpu_observations)
                                item["cpu"]["status"] = "partial" if item["cpu"]["successful_samples"] else "unmeasured"
                                item["cpu"]["window_seconds"] = cpu_ended - cpu_started if cpu_started is not None and cpu_ended is not None else None
                            _stop(browser, psutil)
                            _stop(backend, psutil)
                            print(f"Runtime measurement: {mode} {item['status']}", flush=True)
            except Exception as error:
                report["error"] = str(error)
                preview_log.flush()
                report["preview_log_tail"] = (temporary / "preview.log").read_text(encoding="utf-8", errors="replace")[-1500:]
            finally:
                _stop(preview, psutil)
    measured = sum(item["status"] == "measured" for item in report["modes"])
    report["status"] = "measured" if measured == len(modes) else "partial" if measured or any(item["status"] == "partial" for item in report["modes"]) else "unmeasured"
    return report
