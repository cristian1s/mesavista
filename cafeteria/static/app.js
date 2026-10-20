const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state, selection, selectedTable='M06', preview=null, cfg, calibrationImage=new Image();
let isBusy=false, toastTimer;
const time = s => new Intl.DateTimeFormat('es-CO',{timeZone:'America/Bogota',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(s));
const seatSvg='<svg viewBox="0 0 24 26" aria-hidden="true"><rect x="4" y="2" width="16" height="13" rx="4"/><rect x="2" y="13" width="20" height="8" rx="3"/><rect x="3" y="22" width="3" height="3" rx="1"/><rect x="18" y="22" width="3" height="3" rx="1"/></svg>';

function toast(message,error=false){$('toast').textContent=message;$('toast').className='toast'+(error?' error':'');$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,error?10000:4500);}
async function api(path,body){const response=await fetch('/api/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!response.ok){let msg;try{msg=(await response.json()).detail}catch{msg=response.statusText}throw Error(typeof msg==='string'?msg:JSON.stringify(msg));}return response.json();}
async function refresh(){state=await api('state');render();}
function page(name){document.querySelectorAll('.page').forEach(p=>p.hidden=p.id!=='page-'+name);document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n.dataset.page===name));$('pageLabel').textContent={panel:'Vista del salón',history:'Historial',calibration:'Configuración de zonas',about:'Acerca del proyecto'}[name];if(name==='calibration'){cfg=structuredClone(state.config);initCalibration();}location.hash=name;}
document.querySelectorAll('.nav').forEach(n=>n.addEventListener('click',()=>page(n.dataset.page)));

function render(){
 const r=state.latest;
 $('modelStatus').textContent=state.model_ready?'Modelo instalado · sin conexión externa':'Falta descargar el modelo';
 $('people').textContent=r?.people??'—';$('occupied').textContent=r?state.tables.filter(t=>t.occupied).length:'—';$('empty').textContent=r?.empty_seats??'—';$('waiting').textContent=r?.waiting??'—';$('waitingBadge').textContent=r?.waiting??'—';
 $('peopleNote').textContent=r?`${r.seated} con asiento asignado · ${r.unassigned} sin asignar`:'Carga una imagen para comenzar';
 $('tableNote').textContent=r?`${state.tables.filter(t=>t.status==='available').length} disponibles · ${state.tables.filter(t=>t.status==='review').length} por revisar`:'Sin observación todavía';
 $('waitingNote').textContent=r?.waiting?'Personas detectadas en la entrada':'Entrada del local';
 $('lastObserved').textContent=r?`Observación ${time(r.timestamp)}`:'Sin imagen analizada';
 $('tableGrid').innerHTML=state.tables.map(t=>`<button class="table-wrap status-${t.status} ${t.id===selectedTable?'selected':''}" data-table="${t.id}" aria-label="${t.id}: ${t.occupied} de 3 asientos ocupados, ${t.status==='unknown'?'sin información':t.status==='review'?'pendiente de revisión':t.status==='occupied'?'ocupada':'disponible'}"><span class="table-label">${t.id}</span><div class="table-furniture"><div class="table-top"><span>${t.id}</span></div>${t.seats.map((s,i)=>`<span title="${s.id}: ${t.status==='unknown'?'sin información':s.occupied?'ocupado':'sin ocupante'}" class="seat seat-${'abc'[i]} ${s.occupied?'is-occupied':t.status==='unknown'?'is-unknown':''}">${seatSvg}</span>`).join('')}</div><span class="table-count">${t.status==='unknown'?'— / 3':`${t.occupied} / 3`}</span></button>`).join('');
 document.querySelectorAll('[data-table]').forEach(b=>b.onclick=()=>{selectedTable=b.dataset.table;render();});
 const t=state.tables.find(t=>t.id===selectedTable);
 const labels={unknown:'Sin imagen analizada',available:'Disponible',occupied:`Ocupada por ${t.occupied} persona(s)`,review:'Sin ocupantes · pendiente de revisión'};
 $('selectedTable').innerHTML=`<div><strong>${t.id}</strong> · ${labels[t.status]}<br>${t.status==='unknown'?'Los asientos aún no se han evaluado.':`${3-t.occupied} asiento(s) sin ocupantes detectados.`}${t.first_observed?`<br>Observada ocupada desde ${time(t.first_observed)} · ${t.observed_span_minutes} min entre observaciones; permanencia no comprobada.`:''}</div>${t.status==='review'?'<button class="button outline" id="confirmReview">✓ Confirmar disponible</button>':''}`;
 if($('confirmReview'))$('confirmReview').onclick=async()=>{try{await api('review/'+t.id,{});await refresh();toast('Disponibilidad confirmada.');}catch(e){toast(e.message,true)}};
 $('alertCount').textContent=state.events.length;
 $('alerts').innerHTML=state.events.slice(0,8).map(a=>`<div class="alert">${esc(a.message)}<small>${time(a.timestamp)}</small></div>`).join('')||'<p class="empty-state">Los cambios y avisos aparecerán aquí.</p>';
 $('sceneGallery').innerHTML=state.scenes.map(s=>`<button class="scene-card ${selection?.file===s.file?'selected':''}" data-scene="${esc(s.file)}"><img src="/scenes/${encodeURIComponent(s.file)}" alt="${esc(s.title)}"><span><b>${esc(s.title.split(' · ')[0])}</b>${esc(s.title.split(' · ')[1])}</span></button>`).join('');
 document.querySelectorAll('[data-scene]').forEach(b=>b.onclick=()=>{const s=state.scenes.find(s=>s.file===b.dataset.scene);selection={file:s.file,name:s.title};$('selectedFile').textContent=s.title;$('analyze').disabled=false;render();});
 $('historyRows').innerHTML=state.history.map(h=>`<tr><td>${time(h.timestamp)}</td><td>${esc(h.name)}</td><td>${h.result.people}</td><td>${new Set(h.result.occupied_seats.map(s=>s.split('-')[0])).size} / 10</td><td>${h.result.waiting}</td><td>${h.result.unassigned}</td><td>${h.result.inference_ms} ms</td></tr>`).join('')||'<tr><td colspan="7">Todavía no hay observaciones.</td></tr>';
 const history=[...state.history].reverse().slice(-20);
 $('chart').innerHTML=history.length?'<div class="bars">'+history.map(h=>{const n=new Set(h.result.occupied_seats.map(s=>s.split('-')[0])).size;return `<div class="bar-group"><div class="bar" style="height:${Math.max(3,n*13)}px" title="${esc(h.name)}: ${n} mesas ocupadas"><span class="bar-value">${n}/10</span></div><span>${time(h.timestamp)}</span></div>`}).join('')+'</div>':'<p class="empty-state">Analiza imágenes para construir el historial.</p>';
 if(r)$('inferenceTime').textContent=`YOLOv8n · ${r.inference_ms} ms`;
}

async function chooseFile(file){if(!file)return;if(!['image/jpeg','image/png'].includes(file.type))return toast('Selecciona una imagen JPG o PNG.',true);if(file.size>15*1024*1024)return toast('La imagen supera 15 MB.',true);const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)});selection={name:file.name,data};$('selectedFile').textContent=file.name;$('analyze').disabled=false;render();}
$('upload').onchange=e=>chooseFile(e.target.files[0]);
$('dropzone').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('upload').click();}};
['dragenter','dragover'].forEach(event=>$('dropzone').addEventListener(event,e=>{e.preventDefault();$('dropzone').classList.add('dragging')}));
['dragleave','drop'].forEach(event=>$('dropzone').addEventListener(event,e=>{e.preventDefault();$('dropzone').classList.remove('dragging');if(event==='drop')chooseFile(e.dataTransfer.files[0]);}));
$('analyze').onclick=async()=>{if(!selection||isBusy)return;isBusy=true;$('busy').hidden=false;$('analyze').disabled=true;try{const r=await api(selection.file?'analyze-scene':'analyze-upload',selection.file?{file:selection.file}:{name:selection.name,data:selection.data});preview=r.preview;$('analysisImage').src=preview;$('analysisImage').hidden=false;$('analysisPlaceholder').hidden=true;await refresh();toast(`Análisis completo: ${r.people} persona(s), ${r.seated} asiento(s) ocupado(s).`);}catch(e){toast(e.message,true)}finally{isBusy=false;$('busy').hidden=true;$('analyze').disabled=!selection}};
$('reset').onclick=async()=>{if(!confirm('¿Borrar el historial y reiniciar el estado de las mesas? Las imágenes y la configuración se conservan.'))return;try{await api('reset',{});preview=null;selection=null;$('analysisImage').hidden=true;$('analysisPlaceholder').hidden=false;$('selectedFile').textContent='Ninguna imagen seleccionada';$('analyze').disabled=true;await refresh();toast('Demo reiniciada. Analiza la escena 00 para comenzar.')}catch(e){toast(e.message,true)}};

function initCalibration(){
 $('seatSelect').innerHTML=cfg.seats.map(s=>`<option value="${s.id}">${s.id}</option>`).join('');$('seatSelect').value='M06-A';$('confidence').value=cfg.confidence;cfg.waiting.forEach((v,i)=>$('wait'+i).value=v);loadSeat();calibrationImage.src=preview||'/scenes/00_base_vacia.png';
}
function loadSeat(){const s=cfg.seats.find(s=>s.id===$('seatSelect').value);$('radiusX').value=s.rx;$('radiusY').value=s.ry;drawCalibration();}
function drawCalibration(){if(!cfg||!calibrationImage.complete||!calibrationImage.naturalWidth)return;const canvas=$('calibrationCanvas');canvas.width=calibrationImage.naturalWidth;canvas.height=calibrationImage.naturalHeight;const ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;ctx.drawImage(calibrationImage,0,0,w,h);const [a,b,c,d]=cfg.waiting;ctx.fillStyle='#e2ad3230';ctx.fillRect(a*w,b*h,(c-a)*w,(d-b)*h);ctx.strokeStyle='#dca32a';ctx.lineWidth=2;ctx.strokeRect(a*w,b*h,(c-a)*w,(d-b)*h);for(const s of cfg.seats){ctx.beginPath();ctx.ellipse(s.x*w,s.y*h,s.rx*w,s.ry*h,0,0,Math.PI*2);ctx.fillStyle=s.id===$('seatSelect').value?'#35af6e40':'#55996a10';ctx.fill();ctx.strokeStyle=s.id===$('seatSelect').value?'#00aa66':'#639878';ctx.lineWidth=s.id===$('seatSelect').value?4:1;ctx.stroke();ctx.fillStyle='#12432a';ctx.font='bold 14px Segoe UI';ctx.fillText(s.id,s.x*w-20,s.y*h);}}
calibrationImage.onload=drawCalibration;
$('seatSelect').onchange=loadSeat;
for(const id of ['radiusX','radiusY'])$(id).onchange=()=>{const s=cfg.seats.find(s=>s.id===$('seatSelect').value);s[id==='radiusX'?'rx':'ry']=Number($(id).value);drawCalibration()};
for(let i=0;i<4;i++)$('wait'+i).onchange=()=>{cfg.waiting[i]=Number($('wait'+i).value);drawCalibration()};
$('calibrationCanvas').onclick=e=>{const rect=e.target.getBoundingClientRect(),s=cfg.seats.find(s=>s.id===$('seatSelect').value);s.x=(e.clientX-rect.left)/rect.width;s.y=(e.clientY-rect.top)/rect.height;drawCalibration()};
$('useLastImage').onclick=()=>{if(!preview)return toast('Primero analiza una imagen.',true);calibrationImage.src=preview};
$('useBaseImage').onclick=()=>calibrationImage.src='/scenes/00_base_vacia.png';
$('saveZones').onclick=async()=>{try{cfg.confidence=Number($('confidence').value);await api('config',cfg);await refresh();toast('Zonas guardadas. Vuelve a analizar la imagen para aplicar los cambios.')}catch(e){toast(e.message,true)}};
refresh().then(()=>page(['panel','history','calibration','about'].includes(location.hash.slice(1))?location.hash.slice(1):'panel')).catch(e=>toast('No se pudo conectar al servidor: '+e.message,true));
