"""Evaluación de la serie de demostración, sin modificar el historial del panel."""
import json
from PIL import Image
import app

EXPECTED = [
    (0, 0, []), (2, 2, []), (2, 0, ['M06-A','M06-B']),
    (3, 0, ['M06-A','M06-B','M06-C']),
    (5, 0, ['M06-A','M06-B','M06-C','M07-A','M07-B']),
    (2, 0, ['M07-A','M07-B']),
]
rows = []
tp = fp = fn = tn = 0
for (filename,title), (people,waiting,seats) in zip(app.SCENES,EXPECTED):
    with Image.open(app.ROOT/'assets'/'scenes'/filename) as im:
        r = app.infer(im.convert('RGB'),app.config())
    expected = set(seats)
    predicted = set(r['occupied_seats'])
    tp += len(expected & predicted)
    fp += len(predicted-expected)
    fn += len(expected-predicted)
    tn += 30-len(expected|predicted)
    rows.append(dict(file=filename, expected=dict(people=people,waiting=waiting,occupied_seats=seats),
                     actual={k:v for k,v in r.items() if k!='preview'},
                     passed=r['people']==people and r['waiting']==waiting and predicted==expected and r['unassigned']==0))
    print(filename, 'PASS' if rows[-1]['passed'] else 'FAIL',
          'personas',r['people'],'asientos',r['occupied_seats'],'espera',r['waiting'])
precision=tp/(tp+fp) if tp+fp else 0
recall=tp/(tp+fn) if tp+fn else 0
output=dict(model='yolov8n.pt',fine_tuned=False,conf=app.config()['confidence'],imgsz=1280,
            note='Evaluación sobre seis escenas sintéticas usadas para calibrar. No es prueba independiente de generalización.',
            metrics=dict(tp=tp,fp=fp,fn=fn,tn=tn,precision=precision,recall=recall,
                         f1=2*precision*recall/(precision+recall) if precision+recall else 0,
                         accuracy=(tp+tn)/(tp+fp+fn+tn),
                         people_count_mae=sum(abs(x['actual']['people']-x['expected']['people']) for x in rows)/len(rows)),
            scenes=rows)
(app.ROOT/'docs').mkdir(exist_ok=True)
(app.ROOT/'docs'/'RESULTADOS.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print('Métricas:',output['metrics'])
if not all(x['passed'] for x in rows):
    raise SystemExit(1)
