const socket = io();
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const params = new URLSearchParams(location.search);
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function toast(msg){const t=$('#toast'); if(!t){alert(msg);return} t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2600)}
function store(k,v){localStorage.setItem(k,v)} function read(k){return localStorage.getItem(k)} function removeStore(k){localStorage.removeItem(k)}
function place(n){return n===1?'1st':n===2?'2nd':n===3?'3rd':`${n}th`}
function timeTenth(ms){const d=new Date(ms); let h=d.getHours(); const ap=h>=12?'PM':'AM'; h=h%12||12; const m=String(d.getMinutes()).padStart(2,'0'); const sec=d.getSeconds()+Math.round(d.getMilliseconds()/100)/10; return `${h}:${m}:${sec.toFixed(1).padStart(4,'0')} ${ap}`}
function dateLabel(ms){return ms?new Date(ms).toLocaleString([], {weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'No scheduled time'}
function dateKey(ms){const d=new Date(ms||Date.now()); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
function dateTabLabel(key){const [y,m,d]=key.split('-').map(Number); return new Date(y,m-1,d).toLocaleDateString([], {weekday:'short',month:'short',day:'numeric'})}
function countdownFrom(left){if(left==null)return 'Waiting'; if(left<=0)return 'Starting'; const t=Math.ceil(left/1000), h=Math.floor(t/3600), m=Math.floor((t%3600)/60), s=t%60; return h?`${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`:`${m}:${String(s).padStart(2,'0')}`}
function countdownTo(ms){return ms?countdownFrom(ms-Date.now()):'Waiting'}
function normPhone(v){return String(v||'').replace(/\D/g,'').slice(-10)}
function playerLinkFor(code){return location.origin+'/player'+(code?`?code=${encodeURIComponent(code)}`:'')}
function qrSrc(url){return `https://api.qrserver.com/v1/create-qr-code/?size=360x360&data=${encodeURIComponent(url)}`}
async function copyText(text,label='Copied'){try{await navigator.clipboard.writeText(text);toast(label)}catch{prompt('Copy this:',text)}}
async function shareNative({title='Barfly Blackout Bingo',text='',url=''}){if(navigator.share){try{await navigator.share({title,text,url});return}catch{}} await copyText(`${text}\n${url}`.trim(),'Share link copied')}
function renderWinners(rows=[]){if(!rows.length)return '<p class="muted">No winners yet.</p>'; return rows.map(w=>`<div class="winner-row"><div class="winner-place">${place(w.place)}</div><div><b>${escapeHtml(w.name)}</b><div class="tiny">Card ${w.cardNumber} • ${timeTenth(w.atMs)}</div>${w.snapshot?.length?`<div class="snapshot"><b>At that moment:</b>${w.snapshot.slice(0,5).map(x=>`<div>${place(x.rank)} — ${escapeHtml(x.name)} — ${x.marked}/25</div>`).join('')}</div>`:''}</div></div>`).join('')}
function renderLeaderboard(list=[]){if(!list.length)return '<p class="muted">No active players yet.</p>'; return list.map((x,i)=>`<div class="leader-row"><div class="rank">${i+1}</div><div class="leader-main"><b>${escapeHtml(x.name)}</b><div class="meter"><span style="width:${Math.round(x.marked/25*100)}%"></span></div><div class="tiny">Best card ${x.cardNumber} • ${x.marked}/25 selected</div></div><div class="pill">${x.marked}/25</div></div>`).join('')}
function renderCumulative(list=[]){if(!list?.length)return '<p class="muted">No cumulative wins yet.</p>'; return list.map((x,i)=>`<div class="leader-row"><div class="rank">${i+1}</div><div class="leader-main"><b>${escapeHtml(x.name)}</b><div class="tiny">${x.wins} cumulative win${x.wins===1?'':'s'}</div></div><div class="pill">${x.wins}</div></div>`).join('')}
