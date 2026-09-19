const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const state={view:'overview',competition:'ALL'};
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const fmtDate=s=>s?new Date(s).toLocaleString('it-IT',{day:'2-digit',month:'2-digit',year:'2-digit',hour:'2-digit',minute:'2-digit'}):'—';
const api=async(path)=>{const r=await fetch(path); if(!r.ok)throw new Error(await r.text()); return r.json()};
const q=()=>`competition=${encodeURIComponent(state.competition)}`;
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2800)}
function panel(title,subtitle,body){return `<div class="panel"><div class="panel-head"><h2>${title}</h2><span>${subtitle||''}</span></div>${body}</div>`}
function table(headers,rows){if(!rows.length)return '<div class="empty">Nessun dato disponibile.</div>';return `<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`}
const seven=x=>(x.seven_scored==null&&x.seven_attempts==null)?'—':`${x.seven_scored??0}/${x.seven_attempts??0}`;
const sevenMatch=(s,a)=>(s==null&&a==null)?'—':`${s??0}/${a??0}`;
function sanctionCell(p,type){
  const xs=(p.sanctions||[]).filter(s=>s.sanction_type===type && !s.is_derived);
  return xs.map(s=>s.minute||'✓').join(', ')||'—';
}
function dqCell(p){
  const direct=(p.sanctions||[]).filter(s=>s.sanction_type==='disqualification'&&!s.is_derived).map(s=>s.minute||'✓');
  const derived=(p.sanctions||[]).filter(s=>s.sanction_type==='disqualification_3x2').map(s=>`${s.minute||'✓'} (3×2′)`);
  return [...direct,...derived].join(', ')||'—';
}
async function overview(){
 const [o,m,teams]=await Promise.all([api('/api/overview?'+q()),api('/api/matches?'+q()),api('/api/team-stats?'+q())]);
 const k=[['Gare',o.played||0,'referti acquisiti'],['Gol',o.goals||0,'stagionali'],["2'",o.two_min||0,'esclusioni'],['Squal.',o.dq||0,`${o.direct_dq||0} dirette + ${o.dq_3x2||0} da 3×2′`],['7 m',`${o.seven_scored||0}/${o.seven_attempts||0}`,'reti/tiri'],['Panchina',o.bench||0,'sanzioni'],['Anomalie',o.issues||0,'da verificare']];
 const recent=m.filter(x=>x.status==='played').slice(-8).reverse().map(x=>`<tr><td><span class="badge gold">${esc(x.competition)}</span></td><td>${fmtDate(x.played_at)}</td><td class="row-title">${esc(x.home_team)}</td><td class="score">${x.home_goals}–${x.away_goals}</td><td class="row-title">${esc(x.away_team)}</td><td>${sevenMatch(x.home_7m_scored,x.home_7m_attempts)} · ${sevenMatch(x.away_7m_scored,x.away_7m_attempts)}</td><td>${esc(x.referees||'—')}</td><td><a class="link" href="#" onclick="showMatch(${x.id});return false">Dettaglio</a></td></tr>`);
 const top=teams.slice().sort((a,b)=>b.two_min-a.two_min).slice(0,8).map(x=>`<tr><td><span class="badge">${esc(x.competition)}</span></td><td class="row-title">${esc(x.team)}</td><td>${x.games}</td><td>${x.gf}</td><td>${seven(x)}</td><td>${x.two_min}</td><td>${x.dq_total}</td><td>${x.bench_sanctions}</td></tr>`);
 $('#content').innerHTML=`<div class="grid-kpi">${k.map(x=>`<div class="kpi"><div class="label">${x[0]}</div><div class="value">${x[1]}</div><div class="sub">${x[2]}</div></div>`).join('')}</div><div class="split">${panel('Ultime gare','dati da referto',table(['Camp.','Data','Casa','Ris.','Trasferta','7m R/T','Arbitri',''],recent))}${panel('Disciplina squadre','ordinate per 2′',table(['Camp.','Squadra','G','GF','7m R/T',"2′",'DQ','Panch.'],top))}</div><div class="last-sync">Ultimo sync: ${o.last_sync?`${fmtDate(o.last_sync.finished_at||o.last_sync.started_at)} · ${esc(o.last_sync.status)} · ${o.last_sync.imported||0} referti`: 'non ancora eseguito'}</div>`;
}
async function matches(){
 const data=await api('/api/matches?'+q());
 const rows=data.map(x=>`<tr><td><span class="badge">${esc(x.competition)}</span></td><td>${x.round_no??'—'}</td><td>${x.match_no??'—'}</td><td>${fmtDate(x.played_at)}</td><td class="row-title">${esc(x.home_team)}</td><td class="score">${x.home_goals??'–'}–${x.away_goals??'–'}</td><td class="row-title">${esc(x.away_team)}</td><td>${sevenMatch(x.home_7m_scored,x.home_7m_attempts)} · ${sevenMatch(x.away_7m_scored,x.away_7m_attempts)}</td><td>${esc(x.referees||'—')}</td><td>${esc(x.delegates||'—')}</td><td><span class="badge ${x.status==='played'?'green':'gold'}">${esc(x.status)}</span></td><td><a class="link" href="#" onclick="showMatch(${x.id});return false">Dettaglio</a> ${x.report_url?`· <a class="link" target="_blank" href="${esc(x.report_url)}">PDF</a>`:''}</td></tr>`);
 $('#content').innerHTML=panel('Registro gare','chiave: competizione + n. gara',table(['Camp.','Giorn.','N.','Data','Casa','Ris.','Trasferta','7m R/T','Arbitri','Delegati','Stato',''],rows));
}
async function teams(){
 const data=await api('/api/team-stats?'+q());
 const rows=data.map(x=>`<tr><td><span class="badge">${esc(x.competition)}</span></td><td class="row-title">${esc(x.team)}</td><td>${x.games}</td><td>${x.gf}</td><td>${x.ga}</td><td>${x.avg_gf}</td><td>${seven(x)}</td><td>${x.two_min}</td><td>${x.direct_dq}</td><td>${x.dq_3x2}</td><td>${x.dq_total}</td><td>${x.bench_sanctions}</td></tr>`);
 $('#content').innerHTML=panel('Statistiche squadra','cumulative stagione · 7m mostrati come reti/tiri',table(['Camp.','Squadra','G','GF','GS','GF/G','7m R/T',"2′",'DQ dir.','DQ 3×2′','DQ tot.','Sanz. panchina'],rows));
}
async function players(){
 const data=await api('/api/players?'+q());
 const rows=data.map(x=>`<tr><td><span class="badge">${esc(x.competition)}</span></td><td class="row-title">${esc(x.name)}</td><td>${esc(x.team)}</td><td>${x.games}</td><td>${x.goals}</td><td>${x.two_min}</td><td>${x.direct_dq}</td><td>${x.dq_3x2}</td></tr>`);
 $('#content').innerHTML=panel('Giocatori','reti e disciplina',table(['Camp.','Giocatore','Squadra','G','Gol',"2′",'DQ dirette','DQ da 3×2′'],rows));
}
async function bench(){
 const data=await api('/api/sanctions?bench_only=true&'+q());
 const rows=data.map(x=>`<tr><td><span class="badge">${esc(x.competition)}</span></td><td>${fmtDate(x.played_at)}</td><td class="row-title">${esc(x.team)}</td><td>${esc(x.official_role||'—')}</td><td class="row-title">${esc(x.person_name)}</td><td><span class="badge red">${esc(x.sanction_type)}</span></td><td>${esc(x.minute||'—')}</td><td>${esc(x.home_team)} – ${esc(x.away_team)}</td><td>${x.report_url?`<a class="link" target="_blank" href="${esc(x.report_url)}">Fonte</a>`:''}</td></tr>`);
 $('#content').innerHTML=panel('Sanzioni panchine','ammonizioni, singolo 2′, squalifiche e relativo minuto',table(['Camp.','Data','Squadra','Ruolo','Ufficiale','Sanzione','Minuto','Gara',''],rows));
}
async function officials(){
 const data=await api('/api/pairs?'+q());
 const rows=data.map(x=>`<tr><td><span class="badge">${esc(x.competition)}</span></td><td>${fmtDate(x.played_at)}</td><td>${x.round_no??'—'}</td><td>${esc(x.home_team)} – ${esc(x.away_team)}</td><td class="row-title">${esc(x.r1||'—')} / ${esc(x.r2||'—')}</td><td>${esc([x.d1,x.d2].filter(Boolean).join(' / ')||'—')}</td><td><a class="link" href="#" onclick="showMatch(${x.id});return false">Dettaglio</a>${x.report_url?` · <a class="link" target="_blank" href="${esc(x.report_url)}">Referto</a>`:''}</td></tr>`);
 $('#content').innerHTML=panel('Arbitri & delegati','storico delle uscite',table(['Camp.','Data','Giorn.','Partita','Coppia','Delegato/i',''],rows));
}
async function quality(){
 const issues=await api('/api/issues');
 const cards=issues.length?issues.map(x=>`<div class="quality-card"><strong>${esc(x.issue_type)} · ${esc(x.severity)}</strong><span>${esc(x.message)}</span></div>`).join(''):'<div class="empty">Nessuna anomalia aperta.</div>';
 $('#content').innerHTML=`${panel('Data quality',`${issues.length} anomalie aperte`,cards)}<div class="panel"><div class="panel-head"><h2>Regole di integrità</h2><span>attive</span></div><div class="quality-card"><strong>Nessuna inferenza silenziosa</strong><span>I campi mancanti restano nulli o vengono segnalati come anomalia.</span></div><div class="quality-card"><strong>Deduplicazione robusta</strong><span>Le tabelle punteggio, timeout, 7m e designazioni non possono più essere interpretate come giocatori.</span></div><div class="quality-card"><strong>Squalifica da terza esclusione</strong><span>Conservata come dato derivato separato dalla colonna “Sq.” del referto.</span></div></div>`;
}
window.showMatch=async function(id){
 $('#page-title').textContent='Dettaglio gara';
 $('#content').innerHTML='<div class="empty">Caricamento referto…</div>';
 try{
   const d=await api(`/api/match/${id}`), m=d.match;
   const assigns=Object.fromEntries(d.assignments.map(a=>[a.role,a.person_name]));
   const roster=side=>d.participants.filter(p=>p.side===side).map(p=>`<tr><td>${esc(p.shirt_no||p.official_role||'—')}</td><td class="row-title">${esc(p.name)}</td><td>${p.person_type==='player'?p.goals:'—'}</td><td>${sanctionCell(p,'warning')}</td><td>${sanctionCell(p,'2min')}</td><td>${dqCell(p)}</td><td>${sanctionCell(p,'san_sq')}</td></tr>`);
   const summary=`<div class="grid-kpi"><div class="kpi"><div class="label">Risultato</div><div class="value">${m.home_goals}–${m.away_goals}</div><div class="sub">${esc(m.home_team)} · ${esc(m.away_team)}</div></div><div class="kpi"><div class="label">7m casa</div><div class="value">${sevenMatch(m.home_7m_scored,m.home_7m_attempts)}</div><div class="sub">reti/tiri</div></div><div class="kpi"><div class="label">7m trasferta</div><div class="value">${sevenMatch(m.away_7m_scored,m.away_7m_attempts)}</div><div class="sub">reti/tiri</div></div><div class="kpi"><div class="label">Arbitri</div><div class="value compact">${esc([assigns['Arbitro 1'],assigns['Arbitro 2']].filter(Boolean).join(' / ')||'—')}</div><div class="sub">coppia</div></div><div class="kpi"><div class="label">Delegato</div><div class="value compact">${esc([assigns['Commissario 1'],assigns['Commissario 2']].filter(Boolean).join(' / ')||'—')}</div><div class="sub">commissario/i</div></div></div>`;
   const a=panel(esc(m.home_team),'A',table(['N°/Ruolo','Nome','Gol','Amm.',"2′",'Sq.','San Sq.'],roster('A')));
   const b=panel(esc(m.away_team),'B',table(['N°/Ruolo','Nome','Gol','Amm.',"2′",'Sq.','San Sq.'],roster('B')));
   $('#content').innerHTML=`<div style="margin-bottom:14px"><a class="link" href="#" onclick="state.view='matches';document.querySelector('[data-view=matches]').click();return false">← Torna alle gare</a>${m.report_url?` · <a class="link" target="_blank" href="${esc(m.report_url)}">Apri referto ufficiale</a>`:''}</div>${summary}<div class="split">${a}${b}</div>`;
 }catch(e){$('#content').innerHTML=`<div class="panel"><div class="empty">Errore: ${esc(e.message)}</div></div>`}
}
const renderers={overview,matches,teams,players,bench,officials,quality};
async function render(){const names={overview:'Panoramica',matches:'Gare',teams:'Squadre',players:'Giocatori',bench:'Panchine',officials:'Arbitri & delegati',quality:'Data quality'};$('#page-title').textContent=names[state.view];$('#content').innerHTML='<div class="empty">Caricamento…</div>';try{await renderers[state.view]()}catch(e){$('#content').innerHTML=`<div class="panel"><div class="empty">Errore: ${esc(e.message)}</div></div>`}}
$$('.nav-item').forEach(b=>b.addEventListener('click',()=>{$$('.nav-item').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.view=b.dataset.view;render()}));
$('#competition').addEventListener('change',e=>{state.competition=e.target.value;render()});
$('#syncBtn').addEventListener('click',async()=>{const b=$('#syncBtn');b.disabled=true;b.textContent='Aggiornamento…';try{const r=await fetch('/api/sync',{method:'POST'});if(!r.ok)throw new Error(await r.text());const out=await r.json();toast((out.result&&out.result.errors)?'Sync completato: alcune fonti da verificare':(out.ok?'Sincronizzazione completata':'Sync completato con errori'));render()}catch(e){toast('Errore durante il sync')}finally{b.disabled=false;b.textContent='Aggiorna FIGH'}});
render();
