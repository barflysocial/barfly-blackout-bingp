const $=(s)=>document.querySelector(s);
const $$=(s)=>Array.from(document.querySelectorAll(s));
function esc(v){return String(v??'').replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function iconPower(n){return {'Freeze':'❄️','Fire':'🔥','Recover':'✚','Second Chance':'🔥'}[n]||'⚡'}
function powerIconMarkup(n){return n==='Recover'?'<span class="recover-badge" aria-hidden="true">✚</span>':`<span class="emoji-icon">${esc(iconPower(n))}</span>`}
function label(n,mode='numbers'){if(!n)return '—'; if(mode==='win'){if(n<=25)return `W-${n}`; if(n<=50)return `I-${n}`; return `N-${n}`} return `${n}`}
function cellLabel(n){return n?`${n}`:'—'}
function fmtSecs(total){total=Math.max(0,Number(total||0));const h=Math.floor(total/3600),m=Math.floor((total%3600)/60),s=Math.floor(total%60);return h?`${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`:`${m}:${String(s).padStart(2,'0')}`}
function displayCall(data){if(data.status==='ended')return 'GAME OVER'; if(data.status==='cancelled')return 'CANCELLED'; if(data.status!=='started')return 'LOBBY'; return data.current_label||'—'}
async function getJSON(url){const r=await fetch(url,{cache:'no-store'});return r.json()}
async function postJSON(url,data){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data||{})});return r.json()}

let timerSync=null;
function syncTimer(data){
  const nowClient=Date.now();
  const serverMs=Date.parse(data.server_now||'');
  const drift=Number.isFinite(serverMs)?nowClient-serverMs:0;
  const wheelActive=!!(data.power_wheel&&data.power_wheel.active);
  timerSync={status:data.status,lobbyPaused:!!data.lobby_paused,countdown:Number(data.countdown||0),lobbyCountdown:data.lobby_countdown, duration:Number(data.countdown_duration||data.countdown||10),wheelActive,callDeadline:null,lobbyDeadline:null};
  const callMs=Date.parse(data.call_ends_at||'');
  const lobbyMs=Date.parse(data.lobby_ends_at||'');
  if(Number.isFinite(callMs)&&!wheelActive)timerSync.callDeadline=callMs+drift;
  if(Number.isFinite(lobbyMs))timerSync.lobbyDeadline=lobbyMs+drift;
}
function timerText(){
  if(!timerSync)return '';
  if(timerSync.status==='ended'||timerSync.status==='cancelled')return '0:00';
  if(timerSync.status!=='started'&&timerSync.lobbyCountdown!==null&&timerSync.lobbyCountdown!==undefined){
    if(timerSync.lobbyPaused)return 'PAUSED';
    if(timerSync.lobbyDeadline)return fmtSecs(Math.ceil((timerSync.lobbyDeadline-Date.now())/1000));
    return fmtSecs(timerSync.lobbyCountdown);
  }
  if(timerSync.status==='started'){
    if(timerSync.wheelActive)return fmtSecs(timerSync.duration);
    if(timerSync.callDeadline)return fmtSecs(Math.ceil((timerSync.callDeadline-Date.now())/1000));
    return fmtSecs(timerSync.countdown);
  }
  return fmtSecs(timerSync.countdown||timerSync.duration||0);
}
function renderTimerNow(){const el=$('#timer'); if(el&&timerSync)el.textContent=timerText()}
function applyCommonData(data){
  if($('#currentNumber'))$('#currentNumber').textContent=displayCall(data);
  if($('#status'))$('#status').textContent=data.status;
  syncTimer(data); renderTimerNow(); showWheel(data.power_wheel);
}

function showWheel(w){const m=$('#powerWheel'); if(!m)return; if(w&&w.active){m.classList.add('show'); $('#wheelAlias').textContent=w.alias||''; $('#wheelPower').innerHTML=`${powerIconMarkup(w.power)} ${esc(w.power||'Power')}`;} else m.classList.remove('show')}
function renderFeed(feed){const el=$('#feed'); if(!el)return; el.innerHTML=(feed||[]).map(f=>`<div>${esc(f.text)}</div>`).join('')||'<div class="small">No activity yet</div>'}
function renderMiniFeed(feed){const el=$('#miniFeed'); if(!el)return; el.innerHTML=(feed||[]).slice(0,3).map(f=>`<div>${esc(f.text)}</div>`).join('')||'<div class="small">No recent activity</div>'}
function renderLeaderboard(lb){
  const rows=lb||[];
  const el=$('#leaderboard');
  if(el) el.innerHTML=rows.map((p,i)=>`<div class="leader-row rankings-row"><b>${i+1}</b><span>${esc(p.alias)}${p.afk?' ⚠️':''}</span><b>${p.lines_left} lines</b><b>${p.points} pts</b></div>`).join('')||'<div class="small">No players yet</div>';
  rows.forEach(p=>{document.querySelectorAll(`.host-player-points[data-player-id="${p.id}"]`).forEach(x=>x.textContent=`${p.points} pts`);});
}

let boardClearedMemo={};
function renderBoard(data){
  const root=$('#cards'); if(!root)return;
  const marked=new Set(data.marked||[]), clovers=new Set(data.clovers||[]), cleared=data.row_credit||{}, called=new Set(data.called||[]);
  const pid=document.body.dataset.playerId || 'global';
  const previous=boardClearedMemo[pid]||{};
  const frozenNow = data.freeze_remaining>0 && data.frozen_number===data.current_number;
  let html='';
  const winHeader = data.board_mode==='win' ? `<div class="win-header"><div>W</div><div>I</div><div>N</div></div>` : '';
  (data.board||[]).forEach((row,ri)=>{
    const key=String(ri), isCleared=!!cleared[key], justCleared=isCleared && !previous[key];
    if(isCleared && !justCleared) return;
    html += `<div class="battle-row ${justCleared?'cleared just-cleared':''}">${row.map(n=>{
      let cls='cell';
      const isFrozenCell = frozenNow && n===data.current_number && !marked.has(n);
      if(marked.has(n))cls+=' marked';
      if(clovers.has(n))cls+=' clover';
      if(called.has(n)&&!marked.has(n))cls+=' called';
      if(n===data.current_number&&!marked.has(n))cls+=' current';
      if(isFrozenCell)cls+=' frozen';
      if(data.mark_mode==='manual'&&!called.has(n)&&!marked.has(n))cls+=' locked';
      if((data.blocked_rows||[]).includes(key))cls+=' blocked';
      const canClick=data.mark_mode==='manual'&&called.has(n)&&!marked.has(n)&&!isFrozenCell;
      return `<button class="${cls}" data-n="${n}" ${canClick?'':'disabled'}>${cellLabel(n)}</button>`
    }).join('')}<span class="line-confetti">🎉</span></div>`;
  });
  boardClearedMemo[pid]={...cleared};
  const freezeNote = frozenNow ? `<div class="freeze-note">❄️ Frozen — you will miss this call unless you use Recover later.</div>` : '';
  root.innerHTML=`${winHeader}${freezeNote}<div class="battle-board board-scroll-area">${html}</div>`;
}
function powerProgress(data){const c=Object.keys(data.row_credit||{}).length; return `${c%3}/3`}
function renderPowers(data,pid){
  const el=$('#powers'); if(!el)return;
  const powers=data.powers||[]; let html='';
  for(let i=0;i<3;i++){
    const p=powers[i];
    html+=p?`<button class="power slot filled power-${esc(p.name).toLowerCase()}" data-power="${esc(p.name)}" title="${esc(p.name)}">${powerIconMarkup(p.name)}<small>${esc(p.name)}</small></button>`:`<div class="power slot empty"><span>＋</span><small>Empty</small></div>`;
  }
  if(data.fire_active) html+=`<div class="power-status fire-active">🔥 Fire Active</div>`;
  el.innerHTML=html;
  $$('.power.filled').forEach(b=>b.onclick=async()=>{const res=await postJSON(`/api/use_power/${pid}`,{name:b.dataset.power}); if(res.message) alert(res.message); if(!res.ok&&res.error) alert(res.error); updatePlayer();});
}
function setTab(id){$$('.tab,.tab-panel').forEach(x=>x.classList.remove('active')); const b=$(`.tab[data-tab="${id}"]`), p=$(`#${id}`); if(b)b.classList.add('active'); if(p)p.classList.add('active')}
$$('.tab').forEach(b=>b.onclick=()=>setTab(b.dataset.tab)); $$('[data-tab-jump]').forEach(b=>b.onclick=()=>setTab(b.dataset.tabJump));

async function updatePlayer(){
  const pid=document.body.dataset.playerId; if(!pid)return;
  const data=await getJSON(`/api/player/${pid}`);
  applyCommonData(data);
  if($('#points'))$('#points').textContent=data.points;
  if($('#linesLeft'))$('#linesLeft').textContent=data.lines_left;
  if($('#progress'))$('#progress').textContent=powerProgress(data);
  renderBoard(data); renderPowers(data,pid); renderLeaderboard(data.leaderboard); renderFeed(data.feed); renderMiniFeed(data.feed);
  if(typeof showClearOutIfNeeded==='function')showClearOutIfNeeded(data);
  if(typeof showPlayerGameOverIfNeeded==='function')showPlayerGameOverIfNeeded(data);
  $$('.cell.current:not(:disabled)').forEach(c=>c.onclick=async()=>{await postJSON(`/api/mark/${pid}`,{number:Number(c.dataset.n)}); updatePlayer();});
}
async function updateGame(){
  const code=document.body.dataset.gameCode; if(!code)return;
  const data=await getJSON(`/api/game/${code}`);
  applyCommonData(data); renderLeaderboard(data.leaderboard); renderFeed(data.feed); renderMiniFeed(data.feed);
  if(typeof showHostGameOverIfNeeded==='function')showHostGameOverIfNeeded(data);
  if(typeof showTvGameOverIfNeeded==='function')showTvGameOverIfNeeded(data);
}
if(document.body.dataset.playerId){updatePlayer();setInterval(updatePlayer,1500)}
else if(document.body.dataset.gameCode){updateGame();setInterval(updateGame,1500)}
setInterval(renderTimerNow,250);

// Clear-out and game-over presentation helpers
function ordinal(n){return n===1?'1st':n===2?'2nd':n===3?'3rd':`${n}th`}
function renderWinnerCards(data){
  const winners=(data.winners||[]).slice(0,3);
  return winners.map(w=>`<div class="winner-card"><h2>${ordinal(Number(w.place))} Place</h2><b>${esc(w.alias)}</b><small>${w.points||0} pts</small></div>`).join('') || '<div class="winner-card"><h2>Game Over</h2><b>No Clear Outs</b></div>';
}
let clearOutShownFor={};
function showClearOutIfNeeded(data){
  const pid=document.body.dataset.playerId;
  if(!pid || !data || !data.clearout_place || clearOutShownFor[pid]) return;
  clearOutShownFor[pid]=true;
  const m=document.getElementById('clearOutModal'); if(!m) return;
  const place=document.getElementById('clearOutPlace'), alias=document.getElementById('clearOutAlias');
  if(place) place.textContent=`${ordinal(Number(data.clearout_place))} Place`;
  if(alias) alias.textContent=data.alias || 'Player';
  m.classList.add('show'); setTimeout(()=>m.classList.remove('show'),5000);
}
let playerGameOverShown=false;
function showPlayerGameOverIfNeeded(data){
  if(!document.body.classList.contains('player-app') || !data || data.status!=='ended' || playerGameOverShown) return;
  playerGameOverShown=true;
  const m=document.getElementById('winnersModal'), wr=document.getElementById('winnerResults'), note=document.getElementById('winnerModalNote'), actions=document.getElementById('winnerActions');
  if(wr) wr.innerHTML=renderWinnerCards(data);
  if(note) note.textContent='Game over. Review the winners or return to RSVP.';
  if(actions) actions.innerHTML='<a class="btn gold" href="/rsvp">Return to RSVP</a>';
  if(m) m.classList.add('show');
}
let hostGameOverShown=false;
function showHostGameOverIfNeeded(data){
  if(!document.body.classList.contains('host-app') || !data || data.status!=='ended' || hostGameOverShown) return;
  hostGameOverShown=true;
  const m=document.getElementById('winnersModal'), wr=document.getElementById('winnerResults'), note=document.getElementById('winnerModalNote'), actions=document.getElementById('winnerActions');
  if(wr) wr.innerHTML=renderWinnerCards(data);
  if(note) note.textContent='Game over. Results are finalized for this session.';
  if(actions) actions.innerHTML=`<a class="btn ghost" href="/host">Back to Sessions</a><a class="btn gold" href="/host/${encodeURIComponent(data.code)}/export.csv">Export Results</a><form method="post" action="/host/${encodeURIComponent(data.code)}/action"><button name="action" value="reset_session" class="ghost">Reset Session</button></form><form method="post" action="/host/${encodeURIComponent(data.code)}/duplicate"><button class="ghost">Duplicate Session</button></form>`;
  if(m) m.classList.add('show');
}
let tvGameOverShown=false;
function showTvGameOverIfNeeded(data){
  if(!document.body.classList.contains('tv-app') || !data || data.status!=='ended' || tvGameOverShown) return;
  tvGameOverShown=true;
  const m=document.getElementById('winnersModal'), wr=document.getElementById('winnerResults'), note=document.getElementById('winnerModalNote'), actions=document.getElementById('winnerActions');
  if(wr) wr.innerHTML=renderWinnerCards(data);
  if(note) note.textContent='Final winner results';
  if(actions) actions.innerHTML='';
  if(m) m.classList.add('show');
}
