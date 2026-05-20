const socket = io();
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const params = new URLSearchParams(location.search);
function toast(msg){const t=$('#toast'); if(!t)return; t.textContent=msg; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),3000)}
function secondsLeft(ts){return Math.max(0, Math.ceil((ts-Date.now())/1000));}
function pctLeft(ts){return Math.max(0, Math.min(100, ((ts-Date.now())/7000)*100));}
function cardShort(id){return '#'+String(id||'').slice(-4).toUpperCase()}
function escapeHtml(s){return String(s).replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
function renderLeaderboard(list=[]){return `<div class="leader">${list.length?list.map((x,i)=>`<div class="leader-row"><div class="rank">${i+1}</div><div><b>${escapeHtml(x.name)}</b><div class="tiny">${cardShort(x.cardId)} • ${x.lines} lines • ${x.marked}/24 marked</div></div><div class="pill">${x.remaining} away</div></div>`).join(''):'<div class="tiny">No approved players yet.</div>'}</div>`}
function setStored(k,v){localStorage.setItem(k,v)} function getStored(k){return localStorage.getItem(k)}
