"""Descarga explícita del modelo público; la aplicación luego funciona sin Internet."""
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parent
target = root / 'models' / 'yolov8n.pt'
target.parent.mkdir(exist_ok=True)
url = 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt'
if not target.exists():
    temp = target.with_suffix('.download')
    print('Descargando YOLOv8n desde Ultralytics…')
    urllib.request.urlretrieve(url, temp)
    temp.replace(target)
print(f'Modelo listo: {target}')
