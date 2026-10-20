# MesaVista

Aplicación local de ocupación de una cafetería de **10 mesas y 30 asientos**. Detecta personas con YOLOv8n y relaciona sus posiciones con zonas configurables de asientos y espera. Incluye un mapa del salón, alertas, historial y exportación CSV.

## Requisitos

- Windows y Python 3.13 de 64 bits, disponible mediante el comando `python`.
- Conexión a Internet durante la instalación de dependencias y descarga del modelo.
- Navegador web.

## Instalación

Clona o descarga el repositorio. Abre una terminal en la carpeta que contiene `app.py` y ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File instalar.ps1
```

El instalador crea `.venv`, instala las dependencias de `requirements-lock.txt` y descarga los pesos oficiales en `models/yolov8n.pt`. Estas carpetas se generan localmente y no forman parte del repositorio.

## Ejecución

1. Abre `INICIAR.cmd` con doble clic.
2. Entra a http://127.0.0.1:8765.
3. Selecciona una escena y pulsa **Analizar con YOLO**.

Para cerrar el servidor, ejecuta `DETENER.cmd`. El primer análisis tarda más porque carga el modelo. Una vez instaladas las dependencias y los pesos, el análisis se realiza localmente.

## Demostración

Analiza las seis escenas en orden:

| Escena | Situación | Personas | Asientos sin ocupantes |
|---|---|---:|---:|
| 00 | Cafetería vacía | 0 | 30 |
| 01 | Dos personas en la entrada | 2 | 30 |
| 02 | Dos personas en M06 | 2 | 28 |
| 03 | Tres personas en M06 | 3 | 27 |
| 04 | M06 y M07 ocupadas | 5 | 25 |
| 05 | Salida de M06, dos personas en M07 | 2 | 28 |

Tras la última escena, M06 queda pendiente de revisión. Selecciona la mesa y confirma su disponibilidad.

Las imágenes de demostración son sintéticas y comparten el mismo encuadre. Estos valores describen las escenas de prueba, no garantizan el rendimiento en otros locales.

## Imágenes propias y configuración

Puedes cargar imágenes JPG o PNG de hasta 15 MB y 25 megapíxeles. En **Configuración de zonas**, ajusta los centros y radios de los treinta asientos, el rectángulo de espera y el umbral de confianza. Guarda los cambios y vuelve a analizar la imagen.

El sistema estima ocupación por posición y no verifica explícitamente la postura sentada. Un cambio de cámara requiere recalibrar las zonas. Una silla sin ocupante puede pertenecer a una mesa ocupada. El personal confirma la limpieza y disponibilidad de las mesas que quedan por revisar.

## Estructura

- `app.py`: servidor FastAPI, inferencia, asignación y persistencia SQLite.
- `static/`: interfaz web.
- `assets/scenes/`: seis escenas de demostración.
- `instalar.ps1` y `download_model.py`: instalación y descarga del modelo.
- `INICIAR.cmd` y `DETENER.cmd`: control del servidor local.
- `evaluate.py`: evaluación de las seis escenas sin modificar el historial del panel.
- `test_project.py`: pruebas de integración con una base de datos separada.
- `requirements-lock.txt`: versiones verificadas de las dependencias.

La aplicación crea `data/` para guardar configuración, observaciones y alertas. No guarda las fotografías subidas en el historial.

## Comprobaciones

Después de instalar, desde la carpeta de la aplicación:

```powershell
.\.venv\Scripts\python.exe test_project.py
.\.venv\Scripts\python.exe evaluate.py
```

La evaluación genera `docs/RESULTADOS.json`, un archivo local excluido del repositorio. Utiliza escenas calibradas y no constituye una validación independiente en cafeterías reales.

## Modelo y alcance

MesaVista utiliza YOLOv8n preentrenado, sin entrenamiento propio. Cada imagen representa una observación puntual: no hay seguimiento de identidad ni comprobación de permanencia entre imágenes.

Consulta la documentación y las condiciones de licencia de Ultralytics en su [repositorio oficial](https://github.com/ultralytics/ultralytics).
