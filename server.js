const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const QRCode = require('qrcode');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = new Server(server);
const PORT = process.env.PORT || 3000;
app.set('trust proxy', true);
app.use(express.static('public'));

function baseUrl(req){ const proto=req.get('x-forwarded-proto')||req.protocol||'https'; return `${proto}://${req.get('host')}`; }
app.get('/', (_,res)=>res.redirect('/player'));
app.get('/player', (req,res)=>{
  const base=baseUrl(req); const html=fs.readFileSync(path.join(__dirname,'public','player.html'),'utf8')
    .replaceAll('__OG_URL__', `${base}${req.originalUrl || '/player'}`)
    .replaceAll('__OG_IMAGE__', `${base}/assets/title.png`);
  res.send(html);
});
app.get('/host', (_,res)=>res.sendFile(path.join(__dirname,'public','host.html')));
app.get('/health', (_,res)=>res.json({ok:true}));

const LETTERS=['B','I','N','G','O'];
const RANGES={B:[1,15],I:[16,30],N:[31,45],G:[46,60],O:[61,75]};
const sessions=new Map();
const BAD=['fuck','shit','bitch','asshole','cunt','dick','pussy','nigger','faggot','whore','slut'];
function id(p=''){return p+crypto.randomBytes(5).toString('hex')}
function code(){let c; do c=String(Math.floor(10000+Math.random()*90000)); while(sessions.has(c)); return c;}
function shuffle(a){const x=[...a]; for(let i=x.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1)); [x[i],x[j]]=[x[j],x[i]];} return x;}
function normPhone(v){return String(v||'').replace(/\D/g,'').slice(-10)}
function maskPhone(v){const p=normPhone(v); return p.length===10?`***-***-${p.slice(-4)}`:'No phone'}
function cleanName(raw,n=0){const s=String(raw||'').trim().replace(/\s+/g,' ').slice(0,24)||`Guest ${String(n+1).padStart(3,'0')}`; const t=s.toLowerCase().replace(/[^a-z0-9]/g,''); return BAD.some(w=>t.includes(w))?`Guest ${String(n+1).padStart(3,'0')}`:s;}
function cleanHandle(raw){return String(raw||'').trim().replace(/\s+/g,' ').slice(0,32)}
function sponsor(x={}){return {name:String(x.name||'').trim(), message:String(x.message||'').trim(), logo:String(x.logo||'').trim()}}
function sponsorsFrom(input=[]){return [0,1,2].map(i=>sponsor(input[i]||{}));}
function playerUrl(s, origin=''){return `${origin}/player?code=${s.code}`}
async function refreshQr(s, origin=''){try{s.qrDataUrl=await QRCode.toDataURL(playerUrl(s,origin),{margin:1,width:360})}catch{}}
function makeDeck(){const a=[]; for(const L of LETTERS){const [lo,hi]=RANGES[L]; for(let n=lo;n<=hi;n++) a.push({letter:L,number:n,code:`${L}-${n}`});} return shuffle(a)}
function cardFromCols(cols){const grid=[]; LETTERS.forEach((L,c)=>cols[c].forEach((n,r)=>{grid[r] ||= []; grid[r].push({letter:L,number:n,code:`${L}-${n}`,called:false,marked:false});})); return {id:id('card_'),grid};}
function makeSingleCard(){return cardFromCols(LETTERS.map(L=>{const [lo,hi]=RANGES[L]; return shuffle(Array.from({length:hi-lo+1},(_,i)=>lo+i)).slice(0,5)}));}
function makeCards(count=3){const n=Math.max(1,Math.min(3,Number(count)||3)); if(n===3){const cols=LETTERS.map(L=>{const [lo,hi]=RANGES[L]; const nums=shuffle(Array.from({length:hi-lo+1},(_,i)=>lo+i)); return [nums.slice(0,5),nums.slice(5,10),nums.slice(10,15)];}); return [0,1,2].map(i=>cardFromCols(cols.map(col=>col[i])));} return Array.from({length:n},makeSingleCard);}
function marked(card){return card.grid.flat().filter(c=>c.marked).length}
function blackout(card){return marked(card)>=25}
function activePlayers(s){return [...s.players.values()].filter(p=>!p.kicked)}
function updateCalled(s,p){for(const card of p.cards) for(const cell of card.grid.flat()) cell.called=s.calledCodes.has(cell.code)}
function bestCard(p){return p.cards.map((c,i)=>({cardId:c.id,cardNumber:i+1,marked:marked(c),remaining:25-marked(c),blackedOut:blackout(c)})).sort((a,b)=>b.marked-a.marked||a.cardNumber-b.cardNumber)[0]||{marked:0,remaining:25,cardNumber:1}}
function alreadyWonRound(s,pid){return s.winners.some(w=>w.playerId===pid)}
function progress(s, excludeWinners=false){const winIds=new Set(s.winners.map(w=>w.playerId)); return activePlayers(s).filter(p=>!excludeWinners||!winIds.has(p.id)).map(p=>({playerId:p.id,name:p.name,...bestCard(p),cards:p.cards.length,cumulativeWins:p.cumulativeWins||0})).sort((a,b)=>b.marked-a.marked||b.cumulativeWins-a.cumulativeWins||a.name.localeCompare(b.name));}
function snapshot(s,winnerId){return progress(s,false).filter(x=>x.playerId!==winnerId).slice(0,5).map((x,i)=>({rank:i+2,playerId:x.playerId,name:x.name,marked:x.marked,remaining:x.remaining,cardNumber:x.cardNumber}));}
function label(s){return s.scheduledAt?`${s.title} — ${new Date(s.scheduledAt).toLocaleString([], {weekday:'short',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})}`:`${s.title} — Code ${s.code}`}
function publicSession(s){const reserved=s.reservations.filter(r=>r.status==='reserved').length; const checked=s.reservations.filter(r=>r.checkedIn).length; return {code:s.code,title:s.title,status:s.status,scheduledAt:s.scheduledAt,timezone:s.timezone,cap:s.cap,reserved,checkedIn:checked,full:reserved>=s.cap,label:label(s),currentCall:s.currentCall,calledCount:s.calledCodes.size,winnersCount:s.winners.length,callIntervalMs:s.callIntervalMs,endResetAt:s.endResetAt};}
function publicSessions(){return [...sessions.values()].filter(s=>!s.archived).sort((a,b)=>(a.scheduledAt||a.createdAt)-(b.scheduledAt||b.createdAt)).map(publicSession)}
function visible(s){return {code:s.code,title:s.title,status:s.status,scheduledAt:s.scheduledAt,timezone:s.timezone,cardsPerPlayer:s.cardsPerPlayer,cap:s.cap,tipLink:s.tipLink,sponsors:s.sponsors,serverNow:Date.now(),currentCall:s.currentCall,callId:s.callId,calledCodes:[...s.calledCodes],winners:s.winners,cumulativeLeaderboard:activePlayers(s).map(p=>({playerId:p.id,name:p.name,wins:p.cumulativeWins||0})).sort((a,b)=>b.wins-a.wins||a.name.localeCompare(b.name)).filter(x=>x.wins>0),leaderboard:progress(s,true).slice(0,10),qrDataUrl:s.qrDataUrl,callIntervalMs:s.callIntervalMs,reservationsCount:s.reservations.length,checkedInCount:s.reservations.filter(r=>r.checkedIn).length,endResetAt:s.endResetAt||null};}
function playerView(s,p){updateCalled(s,p); return {session:visible(s),player:{id:p.id,name:p.name,cards:p.cards,kicked:!!p.kicked,cumulativeWins:p.cumulativeWins||0},myBest:bestCard(p)}}
function hostView(s){return {session:visible(s),players:activePlayers(s).map(p=>({id:p.id,name:p.name,cardCount:p.cards.length,best:bestCard(p),cumulativeWins:p.cumulativeWins||0})),reservations:s.reservations.map(r=>({id:r.id,name:r.name,phoneMasked:maskPhone(r.phone),social:r.social,status:r.status,checkedIn:r.checkedIn,playerId:r.playerId,createdAt:r.createdAt})),hostLog:s.hostLog.slice(-80)}}
function emitHost(s){io.to(`host:${s.code}`).emit('hostState',hostView(s)); io.to('host:lobby').emit('hostSessions',publicSessions())}
function emitPlayers(s){for(const p of activePlayers(s)) io.to(`player:${p.id}`).emit('playerState',playerView(s,p)); io.to(`session:${s.code}`).emit('sessionState',visible(s))}
function emitAll(s){emitHost(s); emitPlayers(s); io.emit('publicSessions',publicSessions())}
function clearBoardKeepPlayers(s, auto=false){if(s.autoTimer)clearInterval(s.autoTimer); s.autoTimer=null; if(s.endTimer)clearTimeout(s.endTimer); s.endTimer=null; s.status='lobby'; s.deck=makeDeck(); s.calledCodes=new Set(); s.currentCall=null; s.callId=0; s.winners=[]; s.endResetAt=null; for(const p of s.players.values()) p.cards=makeCards(s.cardsPerPlayer); s.hostLog.push(auto?'Board auto-cleared. Players and cumulative wins kept.':'New round created. Players and cumulative wins kept.'); emitAll(s)}
function clearPlayersScores(s){clearBoardKeepPlayers(s,false); s.players=new Map(); s.reservations.forEach(r=>{r.checkedIn=false; r.playerId=null}); s.hostLog.push('Players and cumulative wins cleared.'); emitAll(s)}
function beginEndCountdown(s){if(s.endTimer)return; if(s.autoTimer)clearInterval(s.autoTimer); s.autoTimer=null; s.status='results'; s.endResetAt=Date.now()+60000; s.hostLog.push('Top 3 filled. Board will clear in 60 seconds.'); s.endTimer=setTimeout(()=>clearBoardKeepPlayers(s,true),60000); emitAll(s)}
function callNext(s){if(s.status!=='running')s.status='running'; const next=s.deck.shift(); if(!next){beginEndCountdown(s); return;} s.currentCall=next; s.callId++; s.calledCodes.add(next.code); for(const p of s.players.values()) updateCalled(s,p); s.hostLog.push(`Called ${next.code}.`); emitAll(s)}
function checkWin(s,p,card){if(!blackout(card)||alreadyWonRound(s,p.id)||s.winners.length>=3)return; const atMs=Date.now(); const w={place:s.winners.length+1,playerId:p.id,name:p.name,cardId:card.id,cardNumber:p.cards.findIndex(c=>c.id===card.id)+1,atMs,snapshot:snapshot(s,p.id)}; s.winners.push(w); p.cumulativeWins=(p.cumulativeWins||0)+1; s.hostLog.push(`${w.place}${w.place===1?'st':w.place===2?'nd':'rd'} place: ${p.name} on Card ${w.cardNumber}.`); if(s.winners.length>=3) beginEndCountdown(s);}
function createPlayer(s,name,res=null){const p={id:id('p_'),name:cleanName(name,s.players.size),cards:makeCards(s.cardsPerPlayer),kicked:false,reservationId:res?.id||null,cumulativeWins:0}; updateCalled(s,p); s.players.set(p.id,p); if(res){res.checkedIn=true; res.playerId=p.id;} s.hostLog.push(`${p.name} checked in.`); return p}
function createSession({title,origin,cardsPerPlayer=3,cap=40,tipLink='',scheduledAt=null,timezone='',sponsors=[],callIntervalMs=7000}){const c=code(); const s={code:c,title:title||'Barfly Blackout Bingo',status:scheduledAt?'scheduled':'lobby',scheduledAt:scheduledAt||null,timezone:timezone||'local',cardsPerPlayer:Math.max(1,Math.min(3,Number(cardsPerPlayer)||3)),cap:Math.max(1,Math.min(500,Number(cap)||40)),tipLink:String(tipLink||'').trim(),sponsors:sponsorsFrom(sponsors),reservations:[],players:new Map(),deck:makeDeck(),calledCodes:new Set(),currentCall:null,callId:0,winners:[],createdAt:Date.now(),qrDataUrl:'',hostLog:['Session created.'],autoTimer:null,endTimer:null,endResetAt:null,callIntervalMs:Math.max(3000,Math.min(60000,Number(callIntervalMs)||7000)),archived:false}; sessions.set(c,s); refreshQr(s,origin).then(()=>emitHost(s)); return s}

setInterval(()=>{const now=Date.now(); for(const s of sessions.values()){if((s.status==='scheduled'||s.status==='lobby')&&s.scheduledAt&&s.scheduledAt<=now){s.status='running'; s.hostLog.push(`Scheduled start time reached. Game auto-started.`); if(!s.currentCall)callNext(s); if(!s.autoTimer)s.autoTimer=setInterval(()=>callNext(s),s.callIntervalMs); emitAll(s)}}},1000);

io.on('connection', socket=>{
  socket.on('listPublicSessions',(_,cb)=>cb?.({ok:true,sessions:publicSessions()}));
  socket.on('hostListSessions',(_,cb)=>{socket.join('host:lobby'); cb?.({ok:true,sessions:publicSessions()})});
  socket.on('createSession',({title,cardsPerPlayer,cap,tipLink,scheduledAtUtc,timezone,sponsors,callIntervalMs,origin},cb)=>{const utc=Number(scheduledAtUtc); const s=createSession({title,origin,cardsPerPlayer,cap,tipLink,scheduledAt:Number.isFinite(utc)&&utc>0?utc:null,timezone,callIntervalMs,sponsors}); socket.join(`host:${s.code}`); cb?.({ok:true,state:hostView(s),code:s.code}); io.emit('publicSessions',publicSessions())});
  socket.on('hostJoin',({code},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); socket.join(`host:${s.code}`); cb?.({ok:true,state:hostView(s)})});
  socket.on('reserveSpot',({code,name,phone,social},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Game not found.'}); const ph=normPhone(phone); if(ph.length!==10)return cb?.({ok:false,error:'Enter a 10-digit phone number.'}); const reserved=s.reservations.filter(r=>r.status==='reserved').length; let r=s.reservations.find(x=>x.phone===ph&&x.status==='reserved'); if(!r&&reserved>=s.cap)return cb?.({ok:false,error:'This game is full.'}); if(r){r.name=cleanName(name,s.reservations.length); r.social=cleanHandle(social); s.hostLog.push(`${r.name} updated an RSVP.`)} else {r={id:id('r_'),name:cleanName(name,s.reservations.length),phone:ph,social:cleanHandle(social),status:'reserved',checkedIn:false,playerId:null,createdAt:Date.now()}; s.reservations.push(r); s.hostLog.push(`${r.name} reserved a spot.`)} emitAll(s); cb?.({ok:true,reservation:{...r,phoneMasked:maskPhone(r.phone)},session:publicSession(s)})});
  socket.on('findReservations',({phone},cb)=>{const ph=normPhone(phone); if(ph.length!==10)return cb?.({ok:false,error:'Enter a 10-digit phone number.'}); const out=[]; for(const s of sessions.values()) for(const r of s.reservations.filter(x=>x.phone===ph)) out.push({reservationId:r.id,code:s.code,title:s.title,scheduledAt:s.scheduledAt,status:s.status,name:r.name,social:r.social,checkedIn:r.checkedIn,playerId:r.playerId,label:label(s)}); out.sort((a,b)=>(a.scheduledAt||0)-(b.scheduledAt||0)); cb?.({ok:true,reservations:out})});
  socket.on('checkInReservation',({code,reservationId},cb)=>{const s=sessions.get(String(code||'').trim()); const r=s?.reservations.find(x=>x.id===reservationId); if(!s||!r)return cb?.({ok:false,error:'Reservation not found.'}); let p=r.playerId?s.players.get(r.playerId):null; if(!p)p=createPlayer(s,r.name,r); socket.join(`player:${p.id}`); socket.join(`session:${s.code}`); emitAll(s); cb?.({ok:true,playerId:p.id,state:playerView(s,p)})});
  socket.on('joinPlayer',({code,name},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); const p=createPlayer(s,name,null); socket.join(`player:${p.id}`); socket.join(`session:${s.code}`); emitAll(s); cb?.({ok:true,playerId:p.id,state:playerView(s,p)})});
  socket.on('resumePlayer',({code,playerId},cb)=>{const s=sessions.get(String(code||'').trim()); const p=s?.players.get(playerId); if(!s||!p||p.kicked)return cb?.({ok:false,error:'Player not found.'}); socket.join(`player:${p.id}`); socket.join(`session:${s.code}`); cb?.({ok:true,state:playerView(s,p)})});
  socket.on('startGame',({code},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); if(s.endTimer){clearTimeout(s.endTimer);s.endTimer=null;s.endResetAt=null} s.status='running'; if(!s.currentCall)callNext(s); emitAll(s); cb?.({ok:true})});
  socket.on('callNext',({code},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); callNext(s); cb?.({ok:true})});
  socket.on('toggleAutoCall',({code,on,ms},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); if(s.autoTimer)clearInterval(s.autoTimer); s.autoTimer=null; if(on){s.callIntervalMs=Math.max(3000,Math.min(60000,Number(ms)||7000)); if(s.status!=='running'||!s.currentCall)callNext(s); s.autoTimer=setInterval(()=>callNext(s),s.callIntervalMs); s.hostLog.push(`Auto-call on every ${(s.callIntervalMs/1000).toFixed(0)} seconds.`)}else s.hostLog.push('Auto-call off.'); emitAll(s); cb?.({ok:true})});
  socket.on('setCallTimer',({code,ms},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); s.callIntervalMs=Math.max(3000,Math.min(60000,Number(ms)||7000)); if(s.autoTimer){clearInterval(s.autoTimer); s.autoTimer=setInterval(()=>callNext(s),s.callIntervalMs)} s.hostLog.push(`Caller timer set to ${(s.callIntervalMs/1000).toFixed(1)} seconds.`); emitAll(s); cb?.({ok:true})});
  socket.on('markNumber',({code,playerId,cardId,cellCode},cb)=>{const s=sessions.get(String(code||'').trim()); const p=s?.players.get(playerId); const card=p?.cards.find(c=>c.id===cardId); if(!s||!p||!card||p.kicked)return cb?.({ok:false,error:'Card not found.'}); if(alreadyWonRound(s,p.id))return cb?.({ok:false,error:'You already placed this round.'}); const cell=card.grid.flat().find(c=>c.code===cellCode); if(!cell)return cb?.({ok:false,error:'Number not found.'}); if(!s.calledCodes.has(cell.code))return cb?.({ok:false,error:'That number has not been called yet.'}); if(cell.marked)return cb?.({ok:false,error:'Already selected.'}); cell.called=true; cell.marked=true; checkWin(s,p,card); emitAll(s); cb?.({ok:true})});
  socket.on('renamePlayer',({code,playerId,name},cb)=>{const s=sessions.get(String(code||'').trim()); const p=s?.players.get(playerId); if(!s||!p)return cb?.({ok:false,error:'Player not found.'}); const old=p.name; p.name=cleanName(name,0); s.winners.forEach(w=>{if(w.playerId===playerId)w.name=p.name}); const r=s.reservations.find(x=>x.playerId===playerId); if(r)r.name=p.name; s.hostLog.push(`Host renamed ${old} to ${p.name}.`); emitAll(s); cb?.({ok:true})});
  socket.on('kickPlayer',({code,playerId},cb)=>{const s=sessions.get(String(code||'').trim()); const p=s?.players.get(playerId); if(!s||!p)return cb?.({ok:false,error:'Player not found.'}); p.kicked=true; io.to(`player:${p.id}`).emit('kicked',{message:'You have been removed from this game by the host.'}); s.hostLog.push(`${p.name} was kicked.`); emitAll(s); cb?.({ok:true})});
  socket.on('endGame',({code},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); beginEndCountdown(s); cb?.({ok:true})});
  socket.on('newRound',({code},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); clearBoardKeepPlayers(s,false); cb?.({ok:true})});
  socket.on('clearGame',({code},cb)=>{const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); clearPlayersScores(s); cb?.({ok:true})});
});

server.listen(PORT,()=>console.log(`Barfly Blackout Bingo running on ${PORT}`));
