"""Windows/Edge integration check with synthetic camera frames and private records.

Run with backend/.venv/Scripts/python.exe from the repository root. Optional
--screenshot writes frontend/.tracking-ui-check.png for visual inspection.
"""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

import cv2
import numpy as np
from websockets.sync.client import connect

frontend = Path(__file__).resolve().parents[1]
root = frontend.parent
sys.path.insert(0, str(root / 'designs'))
from run import load_design


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def png_url(image):
    ok, encoded = cv2.imencode('.png', image)
    if not ok:
        raise RuntimeError('Could not encode fixture')
    return 'data:image/png;base64,' + base64.b64encode(encoded).decode()


marker0 = png_url(load_design('aruco').generate_marker(0))
marker1 = png_url(load_design('aruco').generate_marker(1))
rng = np.random.default_rng(71)
texture = png_url(cv2.GaussianBlur(rng.integers(0, 256, (240, 320, 3), np.uint8), (3, 3), 0))
injection = r'''(() => {
  const images = SOURCES.map(url => new Promise(resolve => {const image=new Image(); image.onload=()=>resolve(image); image.src=url;}));
  const canvas=document.createElement('canvas'); canvas.width=1280; canvas.height=720;
  const context=canvas.getContext('2d'); let pictures=[];
  window.__scene='marker0'; window.__markerX=800; window.__trackingFrameCount=0; window.__trackingSockets=[];
  function draw() {
    context.fillStyle='#858d85'; context.fillRect(0,0,1280,720);
    if(window.__scene==='marker0' && pictures[0]) context.drawImage(pictures[0],window.__markerX,240,240,240);
    if(window.__scene==='marker1' && pictures[1]) context.drawImage(pictures[1],800,240,240,240);
    if(window.__scene==='texture' && pictures[2]) context.drawImage(pictures[2],720,180,480,360);
  }
  const loaded=Promise.all(images).then(values=>{pictures=values;draw();});
  setInterval(draw,50);
  navigator.mediaDevices.getUserMedia=async()=>{
    await loaded; const stream=canvas.captureStream(12); const track=stream.getVideoTracks()[0];
    const settings=track.getSettings.bind(track); track.getSettings=()=>({...settings(),deviceId:'tracking-test-camera'});
    window.__stream=stream; return stream;
  };
  navigator.mediaDevices.enumerateDevices=async()=>[{kind:'videoinput',deviceId:'tracking-test-camera',label:'Synthetic browser test camera',groupId:'test'}];
  const NativeSocket=window.WebSocket;
  window.WebSocket=class extends NativeSocket {
    constructor(url,...args){super(url,...args);this.isTracking=String(url).includes('/api/ws/tracking');if(this.isTracking)window.__trackingSockets.push(this);}
    send(data){if(this.isTracking && data instanceof Blob)window.__trackingFrameCount++;super.send(data);}
  };
})();'''.replace('SOURCES', json.dumps([marker0, marker1, texture]))

processes = []
checks = []
exceptions = []
with tempfile.TemporaryDirectory(prefix='pupvitals-tracking-browser-', ignore_cleanup_errors=True) as directory:
    task_dir = Path(directory).resolve()
    if task_dir.parent != Path(tempfile.gettempdir()).resolve():
        raise RuntimeError('Unexpected temporary workspace')
    backend_port, frontend_port = free_port(), free_port()
    config = task_dir / 'vite.config.mjs'
    plugin = (frontend / 'node_modules/@vitejs/plugin-react/dist/index.js').as_uri()
    config.write_text('import react from '+json.dumps(plugin)+';export default '+
        '{plugins:[react()],root:'+json.dumps(frontend.as_posix())+
        ',server:{proxy:{"/api":{target:'+json.dumps(f'http://127.0.0.1:{backend_port}')+',ws:true}}}};', encoding='utf-8')
    backend_log = (task_dir / 'backend.log').open('w')
    vite_log = (task_dir / 'vite.log').open('w')
    try:
        backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--app-dir', str(root / 'backend'),
            '--host', '127.0.0.1', '--port', str(backend_port), '--ws', 'websockets-sansio', '--log-level', 'warning'],
            env={**os.environ, 'ASSESSMENT_DB_PATH': str(task_dir / 'private.sqlite3')},
            stdout=backend_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(backend)
        vite = subprocess.Popen(['node.exe', str(frontend / 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1',
            '--port', str(frontend_port), '--strictPort', '--config', str(config)], cwd=frontend,
            stdout=vite_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(vite)
        for url in (f'http://127.0.0.1:{backend_port}/api/health', f'http://127.0.0.1:{frontend_port}'):
            deadline=time.monotonic()+30
            while True:
                try:
                    with urlopen(url,timeout=.5): break
                except OSError:
                    if time.monotonic()>deadline: raise TimeoutError('Isolated service did not start: '+url)
                    time.sleep(.1)
        profile=task_dir/'edge'
        browser=subprocess.Popen(['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','--headless=new',
            '--no-first-run','--no-default-browser-check','--disable-extensions','--disable-background-networking',
            '--enable-unsafe-swiftshader','--use-angle=swiftshader','--remote-debugging-port=0',
            f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(browser)
        deadline=time.monotonic()+25
        while not (profile/'DevToolsActivePort').is_file():
            if time.monotonic()>deadline: raise TimeoutError('Browser did not start')
            time.sleep(.1)
        port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
        with urlopen(f'http://127.0.0.1:{port}/json') as response:
            page=next(item for item in json.load(response) if item['type']=='page')
        with connect(page['webSocketDebuggerUrl'],open_timeout=5) as connection:
            sequence=0
            def cdp(method,params=None):
                global sequence
                sequence+=1
                connection.send(json.dumps({'id':sequence,'method':method,'params':params or {}}))
                while True:
                    result=json.loads(connection.recv(timeout=20))
                    if result.get('method')=='Runtime.exceptionThrown': exceptions.append(result['params']['exceptionDetails'])
                    if result.get('id')==sequence:
                        if 'error' in result: raise RuntimeError(result['error'])
                        return result.get('result',{})
            def evaluate(expression):
                result=cdp('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
                if 'exceptionDetails' in result: raise RuntimeError(result['exceptionDetails'])
                return result.get('result',{}).get('value')
            def wait(expression,timeout=12):
                deadline=time.monotonic()+timeout
                while time.monotonic()<deadline:
                    if evaluate(expression): return
                    time.sleep(.1)
                diagnostics = evaluate("Promise.all([fetch('/api/health').then(async r=>({status:r.status,body:await r.text()})).catch(e=>String(e)),Promise.resolve(window.__trackingSockets.map(s=>({url:s.url,state:s.readyState})))])")
                raise AssertionError('Timed out: '+expression+'\nDiagnostics: '+str(diagnostics)+'\nExceptions: '+str(exceptions)+'\nState: '+str(evaluate('document.body.innerText.slice(-2200)')))
            def check(name,expression):
                wait(expression)
                checks.append(name); print('PASS '+name,flush=True)
            def mode(value):
                evaluate(f"(() => {{const s=document.querySelector('.tracking-settings select');s.value={json.dumps(value)};s.dispatchEvent(new Event('change',{{bubbles:true}}));}})()")
            def select_region(scene_after_open=None):
                evaluate("document.getElementById('tracking-select-region').click()")
                wait("document.querySelector('.tracking-selection-screen canvas')!==null")
                if scene_after_open:
                    evaluate('window.__scene='+json.dumps(scene_after_open))
                    check('region selection shows the live camera after the scene changes',"(() => {const c=document.querySelector('.tracking-selection-screen canvas');const d=c.getContext('2d').getImageData(372,100,216,160).data;let low=255,high=0;for(let i=0;i<d.length;i+=4){low=Math.min(low,d[i]);high=Math.max(high,d[i]);}return high-low>30;})()")
                time.sleep(.2)
                rect=evaluate("(() => {const r=document.querySelector('.tracking-selection-screen canvas').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};})()")
                x0,y0=rect['x']+rect['w']*372/640,rect['y']+rect['h']*100/360
                x1,y1=rect['x']+rect['w']*588/640,rect['y']+rect['h']*260/360
                cdp('Input.dispatchMouseEvent',{'type':'mousePressed','x':x0,'y':y0,'button':'left','buttons':1,'clickCount':1})
                cdp('Input.dispatchMouseEvent',{'type':'mouseMoved','x':x1,'y':y1,'button':'left','buttons':1})
                cdp('Input.dispatchMouseEvent',{'type':'mouseReleased','x':x1,'y':y1,'button':'left','buttons':0,'clickCount':1})
                wait("!document.querySelector('.tracking-selection-card .primary').disabled")
                evaluate("document.querySelector('.tracking-selection-card .primary').click()")
            cdp('Runtime.enable');cdp('Page.enable')
            cdp('Emulation.setDeviceMetricsOverride',{'width':1440,'height':900,'deviceScaleFactor':1,'mobile':False})
            cdp('Page.addScriptToEvaluateOnNewDocument',{'source':injection})
            cdp('Page.navigate',{'url':f'http://127.0.0.1:{frontend_port}'})
            wait("document.querySelector('.app.is-live')!==null",20)
            evaluate("[...document.querySelectorAll('nav button')].find(b=>b.textContent.trim()==='Settings').click()")
            wait("document.querySelector('.tracking-settings select')!==null")
            check('four design choices are visible in Settings',"document.querySelector('.tracking-settings select').options.length===4")
            check('fresh page starts in Normal mode',"document.querySelector('.tracking-settings select').value==='normal'")
            time.sleep(.4)
            check('Normal sends no tracking frames',"window.__trackingFrameCount===0 && window.__trackingSockets.length===0")
            mode('aruco')
            wait("document.querySelector('[data-tracking-mode=aruco]:not([hidden]) .dummy-overlay canvas')!==null && document.querySelector('.tracking-state.is-tracked')!==null",20)
            check('ArUco target enables the frontend dog',"document.querySelector('.tracking-state.is-tracked')!==null")
            check('tracking selector is at the top of Settings',"document.querySelector('.tracking-settings').getBoundingClientRect().top<400")
            evaluate("window.__scene='blank'")
            wait("document.querySelector('.tracked-overlay-plane:not([hidden])')===null")
            check('target loss removes dog and outline',"document.querySelector('.tracking-state').textContent.includes('Target lost')")
            evaluate("window.__scene='marker1'");time.sleep(.7)
            check('wrong marker ID keeps dog hidden',"document.querySelector('.tracked-overlay-plane:not([hidden])')===null")
            evaluate("window.__scene='marker0'")
            wait("document.querySelector('[data-tracking-mode=aruco]:not([hidden])')!==null")
            check('ArUco reacquires marker zero',"document.querySelector('.tracking-state.is-tracked')!==null")
            before=evaluate("parseFloat(document.querySelector('.tracked-overlay-plane .dummy-overlay').style.left)")
            evaluate("window.__markerX=860");time.sleep(.6)
            check('dog follows target translation',f"parseFloat(document.querySelector('.tracked-overlay-plane .dummy-overlay').style.left)>{before+2}")
            evaluate("[...document.querySelectorAll('label')].find(l=>l.textContent==='Mirror camera').querySelector('input').click()")
            check('camera and tracked dog mirror together',"document.querySelector('.camera-feed.mirrored')!==null && document.querySelector('.tracked-overlay-plane.mirrored')!==null")
            evaluate("[...document.querySelectorAll('label')].find(l=>l.textContent==='Mirror camera').querySelector('input').click()")
            mode('normal');time.sleep(.2)
            count=evaluate('window.__trackingFrameCount');time.sleep(.4)
            check('Normal stops tracking traffic and clears tracked placement',f"window.__trackingFrameCount==={count} && document.querySelector('.tracked-overlay-plane')===null")
            evaluate("document.querySelector('.settings-section').open=true")
            wait("[...document.querySelectorAll('label')].some(l=>l.textContent==='Preview for alignment')")
            evaluate("[...document.querySelectorAll('label')].find(l=>l.textContent==='Preview for alignment').querySelector('input').click()")
            wait("document.querySelector('.dummy-overlay canvas')!==null")
            check('Normal manual alignment preview still works',"document.querySelector('.tracked-overlay-plane')===null")
            evaluate("document.querySelector('.settings-section').open=false;window.__scene='texture'");time.sleep(.3)
            mode('orb')
            wait("document.querySelector('.tracking-state').textContent.includes('Select pad region')")
            check('ORB waits for manual selection with no old ArUco dog',"document.querySelector('.tracked-overlay-plane:not([hidden])')===null")
            select_region()
            wait("document.querySelector('[data-tracking-mode=orb]:not([hidden]) .dummy-overlay canvas')!==null && document.querySelector('.tracking-state.is-tracked')!==null",20)
            check('ORB frontend tracks a selected synthetic surface',"document.querySelector('.tracking-state.is-tracked')!==null")
            evaluate("window.__scene='blank'")
            wait("document.querySelector('.tracked-overlay-plane:not([hidden])')===null")
            evaluate("window.__scene='texture'")
            wait("document.querySelector('[data-tracking-mode=orb]:not([hidden])')!==null")
            check('ORB reacquires its selected reference',"document.querySelector('.tracking-state.is-tracked')!==null")
            mode('optical-flow')
            wait("document.querySelector('.tracking-state').textContent.includes('Select pad region')")
            evaluate("window.__scene='blank'")
            wait("(() => {const c=document.createElement('canvas');c.width=32;c.height=24;const x=c.getContext('2d');x.drawImage(document.querySelector('video'),720,180,480,360,0,0,32,24);const d=x.getImageData(0,0,32,24).data;let low=255,high=0;for(let i=0;i<d.length;i+=4){low=Math.min(low,d[i]);high=Math.max(high,d[i]);}return high-low<5;})()")
            select_region('texture')
            wait("document.querySelector('[data-tracking-mode=optical-flow]:not([hidden]) .dummy-overlay canvas')!==null && document.querySelector('.tracking-state.is-tracked')!==null",20)
            check('flow initializes from the frame at confirmation rather than the old opening snapshot',"document.querySelector('.tracking-state.is-tracked')!==null")
            check('flow frontend tracks selected points',"document.querySelector('.tracking-state.is-tracked')!==null")
            evaluate("window.__scene='blank'")
            wait("document.querySelector('.tracking-state').textContent.includes('Target lost')")
            evaluate("window.__scene='texture'");time.sleep(.7)
            check('flow remains lost until selected again',"document.querySelector('.tracked-overlay-plane:not([hidden])')===null")
            select_region()
            wait("document.querySelector('[data-tracking-mode=optical-flow]:not([hidden])')!==null")
            check('manual reselection restores flow tracking',"document.querySelector('.tracking-state.is-tracked')!==null")
            evaluate("window.__trackingSockets.at(-1).close()")
            wait("document.querySelector('.tracking-state').textContent.includes('Select pad region')")
            check('flow disconnect clears target and requires selection',"document.querySelector('.tracked-overlay-plane:not([hidden])')===null")
            evaluate("window.__scene='blank'");mode('orb')
            wait("(() => {const c=document.createElement('canvas');c.width=32;c.height=24;const x=c.getContext('2d');x.drawImage(document.querySelector('video'),720,180,480,360,0,0,32,24);const d=x.getImageData(0,0,32,24).data;let low=255,high=0;for(let i=0;i<d.length;i+=4){low=Math.min(low,d[i]);high=Math.max(high,d[i]);}return high-low<5;})()")
            select_region()
            wait("document.querySelector('.tracking-state').textContent.includes('few features')")
            check('ORB rejection exposes the actual reference-point count',"document.querySelector('.tracking-state').textContent.includes('Usable reference points: 0 / 24')")
            check('featureless selection is rejected visibly',"document.querySelector('.tracked-overlay-plane:not([hidden])')===null")
            mode('normal')
            cdp('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
            check('mobile layout has no horizontal overflow',"document.documentElement.scrollWidth<=window.innerWidth")
            check('mode selector remains reachable on mobile',"document.querySelector('.tracking-settings select').getBoundingClientRect().width>100")
            if '--screenshot' in sys.argv:
                screenshot=cdp('Page.captureScreenshot',{'format':'png'})
                (frontend/'.tracking-ui-check.png').write_bytes(base64.b64decode(screenshot['data']))
            if exceptions: raise AssertionError('Browser exceptions: '+json.dumps(exceptions))
            print(f'Completed {len(checks)} browser checks with real OpenCV and a synthetic camera; no browser exceptions.',flush=True)
    finally:
        failed = sys.exc_info()[0] is not None
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=8)
                except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
        backend_log.close();vite_log.close()
        if failed:
            print('BACKEND LOG: '+(task_dir/'backend.log').read_text(errors='replace')[-6000:],flush=True)
            print('VITE LOG: '+(task_dir/'vite.log').read_text(errors='replace')[-6000:],flush=True)
