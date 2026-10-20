"""MesaVista: detección real de personas y ocupación por zonas configurables."""
from pathlib import Path
from datetime import datetime, timezone
from io import BytesIO, StringIO
from contextlib import contextmanager
import base64
import csv
import json
import math
import os
import sqlite3
import threading
import time

ROOT = Path(__file__).resolve().parent
(ROOT / 'data' / 'yolo').mkdir(parents=True, exist_ok=True)
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'data' / 'yolo'))
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw

DATA = Path(os.environ.get('MESAVISTA_DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'mesavista.sqlite3'
LOCK = threading.RLock()
MODEL = None

SCENES = [
    ('00_base_vacia.png', '00 · Cafetería vacía'),
    ('01_dos_en_espera.png', '01 · Dos personas en espera'),
    ('02_dos_en_M06.png', '02 · Dos personas en M06'),
    ('03_tres_en_M06.png', '03 · M06 completa'),
    ('04_M06_y_M07.png', '04 · Dos mesas ocupadas'),
    ('05_salida_M06.png', '05 · Salida de M06'),
]


def default_config():
    # Centros aproximados del cuerpo sentado, no del mueble. Ajustables en el panel.
    rows = [([.195, .335, .49, .644, .79], .30, .36, .045),
            ([.125, .325, .505, .695, .881], .59, .66, .055)]
    seats = []
    for row, (centers, yside, yfront, offset) in enumerate(rows):
        for col, x in enumerate(centers):
            tid = f'M{row * 5 + col + 1:02}'
            for pos, sx, sy in [('A', x-offset, yside), ('B', x+offset, yside), ('C', x, yfront)]:
                seats.append(dict(id=f'{tid}-{pos}', table=tid, position=pos,
                                  x=sx, y=sy, rx=.042, ry=.09))
    return dict(seats=seats, waiting=[.85, .12, 1., .54], confidence=.35)


@contextmanager
def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        with c:
            yield c
    finally:
        c.close()


with connect() as c:
    c.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, config TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS observations (id INTEGER PRIMARY KEY, timestamp TEXT, name TEXT, result TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, timestamp TEXT, message TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS reviews (table_id TEXT PRIMARY KEY, pending INTEGER NOT NULL)')
    c.execute('INSERT OR IGNORE INTO settings VALUES (1, ?)', (json.dumps(default_config()),))


def config():
    with connect() as c:
        return json.loads(c.execute('SELECT config FROM settings WHERE id=1').fetchone()[0])


def last_result():
    with connect() as c:
        row = c.execute('SELECT id,timestamp,name,result FROM observations ORDER BY id DESC LIMIT 1').fetchone()
    if not row:
        return None
    r = json.loads(row['result'])
    r.update(id=row['id'], timestamp=row['timestamp'], name=row['name'])
    return r


def table_states(result=None):
    result = result or last_result()
    occupied = set(result['occupied_seats']) if result else set()
    with connect() as c:
        pending = {r['table_id'] for r in c.execute('SELECT table_id FROM reviews WHERE pending=1')}
        observations = [(row['timestamp'], {s.split('-')[0] for s in json.loads(row['result'])['occupied_seats']})
                        for row in c.execute('SELECT timestamp,result FROM observations ORDER BY id DESC')]
    out = []
    for n in range(1, 11):
        tid = f'M{n:02}'
        seats = [f'{tid}-{p}' for p in 'ABC']
        count = sum(s in occupied for s in seats)
        status = 'occupied' if count else ('review' if tid in pending else ('available' if result else 'unknown'))
        first = None
        if count:
            for timestamp, tables in observations:
                if tid not in tables:
                    break
                first = timestamp
        span = round((datetime.fromisoformat(result['timestamp'])-datetime.fromisoformat(first)).total_seconds()/60, 1) if first else 0
        out.append(dict(id=tid, occupied=count, status=status,
                        first_observed=first, observed_span_minutes=span,
                        seats=[dict(id=s, occupied=s in occupied) for s in seats]))
    return out


def assign_detections(detections, cfg):
    """Asignación uno a uno por distancia elíptica. Espera tiene prioridad."""
    waiting, outside, candidates = [], [], []
    for i, d in enumerate(detections):
        x, y = d['anchor']
        a, b, c, e = cfg['waiting']
        if a <= x <= c and b <= y <= e:
            waiting.append(i)
            continue
        options = []
        for s in cfg['seats']:
            distance = math.hypot((x-s['x']) / s['rx'], (y-s['y']) / s['ry'])
            if distance <= 1:
                options.append((distance, i, s['id']))
        if options:
            candidates.extend(options)
        else:
            outside.append(i)
    used_people, used_seats = set(), set()
    for distance, i, sid in sorted(candidates):
        if i not in used_people and sid not in used_seats:
            used_people.add(i)
            used_seats.add(sid)
            detections[i]['seat'] = sid
    unassigned = sorted(set(range(len(detections))) - set(waiting) - used_people)
    for i in waiting:
        detections[i]['zone'] = 'waiting'
    for i in unassigned:
        detections[i]['zone'] = 'unassigned'
    return sorted(used_seats), waiting, unassigned


def get_model():
    global MODEL
    if MODEL is None:
        from ultralytics import YOLO
        path = ROOT / 'models' / 'yolov8n.pt'
        if not path.exists():
            raise RuntimeError('Falta models/yolov8n.pt. Ejecuta instalar.ps1 con conexión a Internet.')
        MODEL = YOLO(str(path))
    return MODEL


def infer(image, cfg):
    start = time.perf_counter()
    result = get_model().predict(image, conf=cfg['confidence'], classes=[0], imgsz=1280,
                                 device='cpu', verbose=False)[0]
    w, h = image.size
    detections = []
    for box, conf in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist()):
        x1, y1, x2, y2 = box
        detections.append(dict(box=[x1/w, y1/h, x2/w, y2/h], confidence=round(conf, 4),
                               anchor=[(x1+x2)/2/w, (y1+y2)/2/h]))
    occupied, waiting, unassigned = assign_detections(detections, cfg)
    preview = image.copy()
    draw = ImageDraw.Draw(preview)
    for i, d in enumerate(detections):
        color = '#159b8c' if d.get('seat') else ('#dd9227' if d.get('zone') == 'waiting' else '#a761da')
        box = [v * (w if j % 2 == 0 else h) for j, v in enumerate(d['box'])]
        draw.rectangle(box, outline=color, width=max(2, w//450))
        label = f"P{i+1} {d['confidence']:.0%} {d.get('seat', d.get('zone', ''))}"
        draw.text((box[0]+3, max(0, box[1]-13)), label, fill=color, stroke_width=1)
        x, y = d['anchor'][0]*w, d['anchor'][1]*h
        draw.ellipse((x-4, y-4, x+4, y+4), fill=color)
    buf = BytesIO()
    preview.save(buf, format='JPEG', quality=88)
    return dict(detections=detections, occupied_seats=occupied,
                people=len(detections), seated=len(occupied), waiting=len(waiting), unassigned=len(unassigned),
                empty_seats=30-len(occupied), inference_ms=round((time.perf_counter()-start)*1000),
                preview='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode())


def analyze(image, name):
    with LOCK:
        try:
            result = infer(image, config())
        except Exception as exc:
            raise HTTPException(503, f'No se pudo analizar la imagen: {exc}') from exc
        previous = last_result()
        before = {s.split('-')[0] for s in previous['occupied_seats']} if previous else set()
        after = {s.split('-')[0] for s in result['occupied_seats']}
        now = datetime.now(timezone.utc).isoformat()
        messages = []
        if result['waiting']:
            messages.append(f"{result['waiting']} persona(s) detectada(s) en la zona de espera.")
        if result['unassigned']:
            messages.append(f"{result['unassigned']} persona(s) sin asiento o zona de espera asignada; revisar detecciones.")
        with connect() as c:
            for tid in sorted(before - after):
                c.execute('INSERT OR REPLACE INTO reviews VALUES (?,1)', (tid,))
                messages.append(f'{tid} quedó sin ocupantes detectados. Confirmar limpieza y disponibilidad.')
            for tid in sorted(after):
                c.execute('INSERT OR REPLACE INTO reviews VALUES (?,0)', (tid,))
            for tid in sorted(after - before):
                count = sum(s.startswith(tid+'-') for s in result['occupied_seats'])
                messages.append(f'{tid} pasó a ocupada por {count} persona(s).')
            stored = {k:v for k,v in result.items() if k != 'preview'}
            cur = c.execute('INSERT INTO observations(timestamp,name,result) VALUES (?,?,?)', (now,name,json.dumps(stored)))
            for msg in messages:
                c.execute('INSERT INTO events(timestamp,message) VALUES (?,?)', (now,msg))
            result.update(id=cur.lastrowid, timestamp=now, name=name, alerts=messages)
        result['tables'] = table_states(result)
        return result


app = FastAPI(title='MesaVista', docs_url='/api/docs')
app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')
app.mount('/scenes', StaticFiles(directory=ROOT/'assets'/'scenes'), name='scenes')


@app.get('/')
def index():
    return FileResponse(ROOT/'static'/'index.html')


@app.get('/api/state')
def state():
    with LOCK, connect() as c:
        observations = [dict(r) for r in c.execute('SELECT id,timestamp,name,result FROM observations ORDER BY id DESC LIMIT 100')]
        for r in observations:
            r['result'] = json.loads(r['result'])
        return dict(application='MesaVista', latest=last_result(), tables=table_states(),
                    history=observations, events=[dict(r) for r in c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 100')],
                    scenes=[dict(file=f, title=t) for f,t in SCENES if (ROOT/'assets'/'scenes'/f).exists()],
                    model_ready=(ROOT/'models'/'yolov8n.pt').exists(), config=config())


class SceneRequest(BaseModel):
    file: str


@app.post('/api/analyze-scene')
def scene(req: SceneRequest):
    if req.file not in [f for f,_ in SCENES]:
        raise HTTPException(400, 'Escena desconocida')
    path = ROOT/'assets'/'scenes'/req.file
    if not path.exists():
        raise HTTPException(404, 'No se encuentra la escena')
    with Image.open(path) as im:
        return analyze(im.convert('RGB'), req.file)


class UploadRequest(BaseModel):
    name: str = Field(max_length=200)
    data: str = Field(max_length=20_000_000)


@app.post('/api/analyze-upload')
def upload(req: UploadRequest):
    try:
        raw = base64.b64decode(req.data.split(',')[-1], validate=True)
        with Image.open(BytesIO(raw)) as im:
            if im.width * im.height > 25_000_000:
                raise ValueError('Imagen demasiado grande (máximo 25 megapíxeles)')
            image = im.convert('RGB')
    except Exception as exc:
        raise HTTPException(400, 'Usa una imagen PNG/JPG válida de hasta 15 MB y 25 megapíxeles.') from exc
    return analyze(image, req.name)


@app.post('/api/review/{tid}')
def review(tid: str):
    with LOCK:
        table = next((t for t in table_states() if t['id']==tid), None)
        if not table or table['status'] != 'review':
            raise HTTPException(400, 'Solo se pueden confirmar mesas pendientes de revisión.')
        with connect() as c:
            c.execute('INSERT OR REPLACE INTO reviews VALUES (?,0)', (tid,))
            c.execute('INSERT INTO events(timestamp,message) VALUES (?,?)',
                      (datetime.now(timezone.utc).isoformat(), f'{tid}: disponibilidad confirmada manualmente.'))
    return {'ok':True}


@app.post('/api/reset')
def reset():
    with LOCK, connect() as c:
        for table in ['observations','events','reviews']:
            c.execute(f'DELETE FROM {table}')
    return {'ok':True}


@app.get('/api/export')
def export():
    buf = StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow(['hora_UTC','imagen','personas','asientos_ocupados','en_espera','sin_asignar','mesas_ocupadas','inferencia_ms'])
    with connect() as c:
        for row in c.execute('SELECT * FROM observations ORDER BY id'):
            r = json.loads(row['result'])
            writer.writerow([row['timestamp'],row['name'],r['people'],r['seated'],r['waiting'],r['unassigned'],
                             len({s.split('-')[0] for s in r['occupied_seats']}),r['inference_ms']])
    return Response('\ufeff'+buf.getvalue(), media_type='text/csv',
                    headers={'Content-Disposition':'attachment; filename="mesavista-historial.csv"'})


class SeatConfig(BaseModel):
    id: str
    table: str
    position: str
    x: float = Field(ge=0,le=1)
    y: float = Field(ge=0,le=1)
    rx: float = Field(gt=0,le=.25)
    ry: float = Field(gt=0,le=.25)


class ConfigRequest(BaseModel):
    seats: list[SeatConfig] = Field(min_length=30,max_length=30)
    waiting: list[float] = Field(min_length=4,max_length=4)
    confidence: float = Field(ge=.1,le=.95)


@app.post('/api/config')
def save_config(req: ConfigRequest):
    expected = {f'M{n:02}-{p}' for n in range(1,11) for p in 'ABC'}
    if {s.id for s in req.seats} != expected or any(s.id != s.table+'-'+s.position for s in req.seats):
        raise HTTPException(400,'Se requieren los 30 asientos M01-A a M10-C.')
    a,b,c,d = req.waiting
    if not (0<=a<c<=1 and 0<=b<d<=1):
        raise HTTPException(400,'La zona de espera debe ser un rectángulo normalizado válido.')
    with LOCK, connect() as conn:
        conn.execute('UPDATE settings SET config=? WHERE id=1',(json.dumps(req.model_dump()),))
    return {'ok':True}


if __name__ == '__main__':
    import uvicorn
    import psutil
    proc = psutil.Process()
    (DATA/'server.json').write_text(json.dumps(dict(pid=proc.pid, started_epoch=proc.create_time(), executable=proc.exe())), encoding='utf-8')
    uvicorn.run(app, host='127.0.0.1', port=8765)
