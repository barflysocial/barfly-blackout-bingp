const socket = io();
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const params = new URLSearchParams(location.search);
function escapeHtml(s){ return String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }
function toast(msg){ const t=$('#toast'); if(!t){ alert(msg); return; } t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2800); }
function store(k,v){ localStorage.setItem(k,v); }
function read(k){ return localStorage.getItem(k); }
function removeStore(k){ localStorage.removeItem(k); }
function placeLabel(n){ return n===1?'1st':n===2?'2nd':n===3?'3rd':`${n}th`; }
function timeTenth(ms){ const d=new Date(ms); let h=d.getHours(); const ampm=h>=12?'PM':'AM'; h=h%12 || 12; const m=String(d.getMinutes()).padStart(2,'0'); const seconds=d.getSeconds() + Math.round(d.getMilliseconds()/100)/10; const s=seconds.toFixed(1).padStart(4,'0'); return `${h}:${m}:${s} ${ampm}`; }
function dateTimeLabel(ms){ if(!ms) return 'No scheduled time'; return new Date(ms).toLocaleString([], { weekday:'short', month:'short', day:'numeric', hour:'numeric', minute:'2-digit' }); }
function countdownText(ms){ if(!ms) return 'Waiting for host'; const left = ms - Date.now(); if(left <= 0) return 'Starting now'; const total = Math.ceil(left/1000); const h=Math.floor(total/3600); const m=Math.floor((total%3600)/60); const s=total%60; return h ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` : `${m}:${String(s).padStart(2,'0')}`; }
function normalizePhone(raw){ return String(raw || '').replace(/\D/g,'').slice(-10); }
function renderWinners(winners=[]){
  if(!winners.length) return '<p class="muted">No winners yet.</p>';
  return winners.map(w => `<div class="winner-row"><div class="winner-place">${placeLabel(w.place)}</div><div><b>${escapeHtml(w.name)}</b><div class="tiny">Card ${w.cardNumber} • ${timeTenth(w.atMs)}</div>${w.snapshot?.length?`<div class="snapshot"><b>At that moment:</b>${w.snapshot.slice(0,3).map(x=>`<div>${placeLabel(x.rank)} pace — ${escapeHtml(x.name)} — ${x.marked}/25</div>`).join('')}</div>`:''}</div></div>`).join('');
}
function renderLeaderboard(list=[]){
  if(!list.length) return '<p class="muted">No active players yet.</p>';
  return list.map((x,i)=>`<div class="leader-row"><div class="rank">${i+1}</div><div class="leader-main"><b>${escapeHtml(x.name)}</b><div class="meter"><span style="width:${Math.round((x.marked/25)*100)}%"></span></div><div class="tiny">Best card ${x.cardNumber} • ${x.marked}/25 selected</div></div><div class="pill">${x.marked}/25</div></div>`).join('');
}
async function copyText(text,label='Copied'){ try{ await navigator.clipboard.writeText(text); toast(label); } catch { prompt('Copy this link:', text); } }
async function shareRich({title='Barfly Blackout Bingo', text='', url=''}){ if(navigator.share){ try{ await navigator.share({title,text,url}); return; }catch(e){} } await copyText(`${text}\n${url}`.trim(), 'Share link copied.'); }
function playerLinkFor(code){ return location.origin + '/player' + (code?`?code=${encodeURIComponent(code)}`:''); }
function qrSrc(url){ return `https://api.qrserver.com/v1/create-qr-code/?size=360x360&data=${encodeURIComponent(url)}`; }
