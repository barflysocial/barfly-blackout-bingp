const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const QRCode = require('qrcode');
const crypto = require('crypto');

const app = express();
const server = http.createServer(app);
const io = new Server(server);
const PORT = process.env.PORT || 3000;

app.use(express.static('public'));
app.get('/', (_, res) => res.redirect('/player.html'));
app.get('/player', (_, res) => res.redirect('/player.html'));
app.get('/host', (_, res) => res.redirect('/host.html'));
app.get('/health', (_, res) => res.json({ ok: true, app: 'Barfly Blackout Bingo' }));

const LETTERS = ['B', 'I', 'N', 'G', 'O'];
const ROWS = 5;
const LETTER_RANGES = { B:[1,15], I:[16,30], N:[31,45], G:[46,60], O:[61,75] };
const CALL_SECONDS = 7;
const CARDS_PER_PLAYER = 3;
const DEFAULT_LOBBY_SECONDS = 120;
const POWER_POOL = ['freeze', 'shield', 'swap', 'steal'];
const WIN_REQUIREMENTS = { blackout: 1, double: 2, triple: 3 };
const sessions = new Map();
const PROFANITY = ['fuck','shit','bitch','asshole','cunt','dick','pussy','nigger','faggot','whore','slut'];

function id(prefix=''){ return prefix + crypto.randomBytes(4).toString('hex'); }
function makeCode(){ let code; do { code = String(Math.floor(10000 + Math.random()*90000)); } while(sessions.has(code)); return code; }
function shuffle(arr){ const a=[...arr]; for(let i=a.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; } return a; }
function sample(arr, count){ return shuffle(arr).slice(0,count); }
function randomPower(){ return POWER_POOL[Math.floor(Math.random()*POWER_POOL.length)]; }
function emptyPowers(){ return { freeze:0, shield:0, swap:0, steal:0 }; }
function cleanName(raw, count){
  let name = String(raw||'').trim().replace(/\s+/g,' ').slice(0,24) || `Guest ${String(count+1).padStart(3,'0')}`;
  const low = name.toLowerCase().replace(/[^a-z0-9]/g,'');
  if(PROFANITY.some(w => low.includes(w))) return `Guest ${String(count+1).padStart(3,'0')}`;
  return name;
}
function makeCard(){
  const columns = LETTERS.map(letter => {
    const [start,end] = LETTER_RANGES[letter];
    return sample(Array.from({length:end-start+1}, (_,i) => {
      const number = start + i;
      return { letter, number, code:`${letter}-${number}` };
    }), ROWS);
  });
  const grid=[];
  for(let r=0;r<ROWS;r++){
    grid.push(LETTERS.map((_,c) => ({ ...columns[c][r], marked:false, called:false, free:false })));
  }
  return { id:id('card_'), grid, powerPath:null, powerAwardsGiven:0, powers:emptyPowers() };
}
function makeDeck(){
  const pool=[];
  for(const letter of LETTERS){ const [start,end]=LETTER_RANGES[letter]; for(let n=start;n<=end;n++) pool.push({letter, number:n, code:`${letter}-${n}`}); }
  return shuffle(pool);
}
function normalizeWinMode(mode){ return WIN_REQUIREMENTS[mode] ? mode : 'blackout'; }
function powerTotal(powers){ return Object.values(powers).reduce((a,b)=>a+b,0); }
function aggregatePowers(p){ const out=emptyPowers(); for(const card of p.cards) for(const k of POWER_POOL) out[k] += card.powers[k] || 0; return out; }
function updateCalledFlags(s,p){ for(const card of p.cards) for(const row of card.grid) for(const cell of row) cell.called = s.calledCodes.has(cell.code); }
function countMarked(card){ return card.grid.flat().filter(c=>c.marked).length; }
function remaining(card){ return card.grid.flat().filter(c=>!c.marked).length; }
function isBlackout(card){ return remaining(card) === 0; }
function blackoutCount(p){ return p.cards.filter(isBlackout).length; }
function horizontalLines(card){ let n=0; for(let r=0;r<ROWS;r++) if(card.grid[r].every(c=>c.marked)) n++; return n; }
function verticalLines(card){ let n=0; for(let c=0;c<LETTERS.length;c++) if(card.grid.every(row=>row[c].marked)) n++; return n; }
function pathLineCount(card){ return card.powerPath === 'horizontal' ? horizontalLines(card) : card.powerPath === 'vertical' ? verticalLines(card) : Math.max(horizontalLines(card), verticalLines(card)); }
function completedLines(card){ return horizontalLines(card) + verticalLines(card); }
function setPowerPathIfNeeded(card){
  if(card.powerPath) return null;
  const h=horizontalLines(card), v=verticalLines(card);
  if(h>0 || v>0){ card.powerPath = h >= v ? 'horizontal' : 'vertical'; return card.powerPath; }
  return null;
}
function awardPowersForCard(s,p,card){
  const newlyLocked = setPowerPathIfNeeded(card);
  if(newlyLocked) s.powerLog.push(`${p.name}'s ${shortCard(card.id)} locked ${newlyLocked.toUpperCase()} power path.`);
  if(!card.powerPath) return;
  const validLines = pathLineCount(card);
  const shouldHaveAwards = Math.max(0, validLines - 2);
  while(card.powerAwardsGiven < shouldHaveAwards){
    const power = randomPower();
    card.powers[power]++;
    card.powerAwardsGiven++;
    s.powerLog.push(`${p.name} earned ${power.toUpperCase()} on ${shortCard(card.id)} after ${validLines} ${card.powerPath} BINGOs.`);
  }
}
function awardAllPowers(s,p){ for(const card of p.cards) awardPowersForCard(s,p,card); }
function playerBest(s,p){
  let best=null;
  for(const card of p.cards){
    const b={ cardId:card.id, lines:completedLines(card), horizontalLines:horizontalLines(card), verticalLines:verticalLines(card), marked:countMarked(card), remaining:remaining(card), blackedOut:isBlackout(card), powerPath:card.powerPath, pathLines:pathLineCount(card) };
    if(!best || b.blackedOut > best.blackedOut || b.lines > best.lines || (b.lines===best.lines && b.marked > best.marked) || (b.lines===best.lines && b.marked===best.marked && b.remaining < best.remaining)) best=b;
  }
  return best || { cardId:null, lines:0, marked:0, remaining:25, blackedOut:false, powerPath:null, pathLines:0 };
}
function leaderboard(s){
  const needed = WIN_REQUIREMENTS[s.winMode];
  return [...s.players.values()].filter(p=>p.approved && !p.kicked).map(p => {
    const blackouts = blackoutCount(p);
    const sortedCards = p.cards.map(c=>({ cardId:c.id, remaining:remaining(c), marked:countMarked(c), lines:completedLines(c), blackedOut:isBlackout(c) })).sort((a,b)=>a.remaining-b.remaining || b.marked-a.marked);
    const focus = sortedCards[Math.min(needed-1, sortedCards.length-1)] || sortedCards[0];
    const totalRemainingForMode = sortedCards.slice(0, needed).reduce((sum,c)=>sum+c.remaining,0);
    return { playerId:p.id, name:p.name, cardId:focus?.cardId, lines:focus?.lines || 0, marked:focus?.marked || 0, remaining:focus?.remaining ?? 25, blackouts, needed, totalRemainingForMode, cards:p.cards.length };
  }).sort((a,b)=> b.blackouts-a.blackouts || a.totalRemainingForMode-b.totalRemainingForMode || b.marked-a.marked || a.cards-b.cards).slice(0,5);
}
function visibleSession(s){ return { code:s.code, title:s.title, status:s.status, winMode:s.winMode, cardsPerPlayer:s.cardsPerPlayer, createdAt:s.createdAt, currentCall:s.currentCall, callId:s.callId, callEndsAt:s.callEndsAt, lobbyEndsAt:s.lobbyEndsAt, calledCodes:[...s.calledCodes], winners:s.winners, playerCount:s.players.size, leaderboard:leaderboard(s), qrDataUrl:s.qrDataUrl, currentFreeze:s.currentFreeze } }
function publicPlayer(p){ return { id:p.id, name:p.name, cardCount:p.cards.length, approved:p.approved, powers:aggregatePowers(p), alreadyWon:p.alreadyWon, blackouts:blackoutCount(p), kicked:!!p.kicked }; }
function playerView(s,p){ updateCalledFlags(s,p); return { session:visibleSession(s), player:{...publicPlayer(p), cards:p.cards, selectedCallId:p.selectedCallId}, myRank:playerBest(s,p) }; }
function hostView(s){
  const players = [...s.players.values()].map(p => ({ ...publicPlayer(p), best:playerBest(s,p), cards:p.cards.map(c=>({id:c.id, lines:completedLines(c), horizontalLines:horizontalLines(c), verticalLines:verticalLines(c), pathLines:pathLineCount(c), powerPath:c.powerPath, marked:countMarked(c), remaining:remaining(c), powers:c.powers, blackedOut:isBlackout(c)})) }));
  return { session:visibleSession(s), players, powerLog:s.powerLog.slice(-40) };
}
function shortCard(id){ return '#' + String(id||'').slice(-4).toUpperCase(); }
function resetPlayerCards(p){ p.cards=Array.from({length:CARDS_PER_PLAYER}, makeCard); p.selectedCallId=null; p.alreadyWon=false; }
function createSession(title, origin, winMode='blackout'){
  const code = makeCode();
  const joinUrl = `${origin || ''}/player.html?code=${code}`;
  const s = { code, title:title||'Barfly Blackout Bingo', cardsPerPlayer:CARDS_PER_PLAYER, winMode:normalizeWinMode(winMode), status:'lobby', createdAt:Date.now(), players:new Map(), deck:makeDeck(), calledCodes:new Set(), currentCall:null, callId:0, callEndsAt:0, lobbyEndsAt:0, interval:null, countdownTimer:null, winners:[], powerLog:['Session created. Show directions before starting.'], qrDataUrl:'', currentFreeze:null };
  sessions.set(code,s);
  QRCode.toDataURL(joinUrl,{margin:1,width:320}).then(url=>{ s.qrDataUrl=url; emitHost(s); });
  return s;
}
function emitHost(s){ io.to(`host:${s.code}`).emit('hostState', hostView(s)); io.to(`session:${s.code}`).emit('sessionState', visibleSession(s)); }
function emitPlayer(s,p){ io.to(`player:${p.id}`).emit('playerState', playerView(s,p)); }
function emitPlayers(s){ for(const p of s.players.values()) if(!p.kicked) emitPlayer(s,p); }
function stopTimer(s){ if(s?.interval) clearInterval(s.interval); if(s) s.interval=null; if(s?.countdownTimer) clearTimeout(s.countdownTimer); if(s) s.countdownTimer=null; }
function nextCall(s){
  if(s.status !== 'running') return;
  const next = s.deck.shift();
  if(!next){ s.status='ended'; stopTimer(s); emitHost(s); emitPlayers(s); return; }
  s.currentCall=next; s.callId++; s.callEndsAt=Date.now()+CALL_SECONDS*1000; s.calledCodes.add(next.code); s.currentFreeze=null;
  for(const p of s.players.values()) p.selectedCallId=null;
  emitHost(s); emitPlayers(s);
}
function startGame(s){ stopTimer(s); s.status='running'; s.lobbyEndsAt=0; nextCall(s); s.interval=setInterval(()=>nextCall(s), CALL_SECONDS*1000); }
function startLobbyCountdown(s, seconds=DEFAULT_LOBBY_SECONDS){
  stopTimer(s); s.status='countdown'; s.currentCall=null; s.callEndsAt=0; s.currentFreeze=null; s.lobbyEndsAt=Date.now()+Math.max(5, Number(seconds)||DEFAULT_LOBBY_SECONDS)*1000;
  s.powerLog.push(`Lobby countdown started for ${Math.round((s.lobbyEndsAt-Date.now())/1000)} seconds.`);
  s.countdownTimer=setTimeout(()=>startGame(s), Math.max(0, s.lobbyEndsAt-Date.now()));
}
function resetRound(s, keepPlayers=true){
  stopTimer(s); s.status='lobby'; s.deck=makeDeck(); s.calledCodes=new Set(); s.currentCall=null; s.callId=0; s.callEndsAt=0; s.lobbyEndsAt=0; s.winners=[]; s.currentFreeze=null; s.powerLog=['New round ready. Everyone has 3 fresh random BINGO cards.'];
  if(keepPlayers){ for(const p of s.players.values()){ if(!p.kicked){ resetPlayerCards(p); p.approved=true; } } } else { s.players.clear(); }
}
function checkAutoWin(s,p){
  if(p.kicked || p.alreadyWon || s.winners.find(w=>w.playerId===p.id)) return;
  const needed = WIN_REQUIREMENTS[s.winMode];
  const blackouts = blackoutCount(p);
  if(blackouts >= needed){
    p.alreadyWon=true;
    const winningCards = p.cards.filter(isBlackout).slice(0, needed).map(c=>c.id);
    const win = { playerId:p.id, name:p.name, at:Date.now(), mode:s.winMode, blackouts, winningCards };
    s.winners.push(win);
    s.powerLog.push(`BINGO BLACKOUT: ${p.name} won ${s.winMode.toUpperCase()} mode with ${blackouts} completed card${blackouts===1?'':'s'}.`);
    stopTimer(s); s.status='ended'; s.currentCall=null; s.callEndsAt=0; s.lobbyEndsAt=0;
  }
}
function consumePowerFromCard(card, power){ if((card.powers[power]||0)>0){ card.powers[power]--; return true; } return false; }
function consumeAnyPower(p, power){ for(const card of p.cards){ if(consumePowerFromCard(card,power)) return card; } return null; }
function stealTarget(s, thiefId){
  const ranked = leaderboard(s).map(r => s.players.get(r.playerId)).filter(p=>p && p.id !== thiefId && !p.kicked && powerTotal(aggregatePowers(p))>0);
  return ranked[0] || null;
}
function randomPowerLocation(p){
  const locs=[];
  for(const card of p.cards) for(const power of POWER_POOL) for(let i=0;i<(card.powers[power]||0);i++) locs.push({card,power});
  return locs[Math.floor(Math.random()*locs.length)];
}

io.on('connection', socket => {
  socket.on('createSession', ({title, origin, winMode}, cb) => { const s=createSession(title, origin, winMode); socket.join(`host:${s.code}`); cb?.({ok:true,state:hostView(s)}); });
  socket.on('joinHost', ({code}, cb) => { const s=sessions.get(String(code)); if(!s) return cb?.({ok:false,error:'Session not found'}); socket.join(`host:${s.code}`); cb?.({ok:true,state:hostView(s)}); });
  socket.on('setWinMode', ({code, winMode}, cb) => { const s=sessions.get(String(code)); if(!s) return cb?.({ok:false,error:'Session not found'}); if(!['lobby','directions','countdown'].includes(s.status)) return cb?.({ok:false,error:'Win mode can only be changed before the game starts.'}); s.winMode=normalizeWinMode(winMode); s.powerLog.push(`Host set mode to ${s.winMode.toUpperCase()}.`); emitHost(s); emitPlayers(s); cb?.({ok:true}); });
  socket.on('joinPlayer', ({code, name}, cb) => { const s=sessions.get(String(code)); if(!s) return cb?.({ok:false,error:'Session not found'}); const safeName=cleanName(name, s.players.size); const p={ id:id('p_'), name:safeName, cards:Array.from({length:CARDS_PER_PLAYER}, makeCard), approved:true, selectedCallId:null, alreadyWon:false, kicked:false }; s.players.set(p.id,p); socket.join(`session:${s.code}`); socket.join(`player:${p.id}`); cb?.({ok:true,playerId:p.id,state:playerView(s,p)}); emitHost(s); emitPlayers(s); });
  socket.on('resumePlayer', ({code, playerId}, cb) => { const s=sessions.get(String(code)); const p=s?.players.get(String(playerId)); if(!s||!p||p.kicked) return cb?.({ok:false,error:'Player not found'}); socket.join(`session:${s.code}`); socket.join(`player:${p.id}`); cb?.({ok:true,state:playerView(s,p)}); });
  socket.on('renamePlayer', ({code, playerId, name}, cb) => { const s=sessions.get(String(code)); const p=s?.players.get(String(playerId)); if(!s||!p) return cb?.({ok:false,error:'Player not found'}); const old=p.name; p.name=cleanName(name, s.players.size); s.powerLog.push(`Host renamed ${old} to ${p.name}.`); emitHost(s); emitPlayers(s); cb?.({ok:true}); });
  socket.on('kickPlayer', ({code, playerId}, cb) => { const s=sessions.get(String(code)); const p=s?.players.get(String(playerId)); if(!s||!p) return cb?.({ok:false,error:'Player not found'}); p.kicked=true; s.powerLog.push(`Host kicked ${p.name} from the session.`); io.to(`player:${p.id}`).emit('kicked', {message:'You have been removed from this game by the host. Please see the host if this was a mistake.'}); s.players.delete(p.id); emitHost(s); emitPlayers(s); cb?.({ok:true}); });
  socket.on('showDirections', ({code}) => { const s=sessions.get(String(code)); if(!s) return; stopTimer(s); s.status='directions'; s.currentCall=null; s.callEndsAt=0; s.lobbyEndsAt=0; s.currentFreeze=null; s.powerLog.push('Directions are showing before the game begins.'); emitHost(s); emitPlayers(s); });
  socket.on('startCountdown', ({code, seconds}) => { const s=sessions.get(String(code)); if(!s) return; startLobbyCountdown(s, seconds); emitHost(s); emitPlayers(s); });
  socket.on('startGame', ({code}) => { const s=sessions.get(String(code)); if(!s) return; startGame(s); });
  socket.on('pauseGame', ({code}) => { const s=sessions.get(String(code)); if(!s) return; stopTimer(s); s.status='paused'; emitHost(s); emitPlayers(s); });
  socket.on('nextCall', ({code}) => { const s=sessions.get(String(code)); if(!s) return; stopTimer(s); s.status='running'; nextCall(s); s.interval=setInterval(()=>nextCall(s), CALL_SECONDS*1000); });
  socket.on('endGame', ({code}) => { const s=sessions.get(String(code)); if(!s) return; stopTimer(s); s.status='ended'; s.currentCall=null; s.callEndsAt=0; s.lobbyEndsAt=0; s.currentFreeze=null; s.powerLog.push('Host ended the game.'); emitHost(s); emitPlayers(s); });
  socket.on('resetRound', ({code}) => { const s=sessions.get(String(code)); if(!s) return; resetRound(s,true); emitHost(s); emitPlayers(s); });
  socket.on('clearPlayersScores', ({code}) => { const s=sessions.get(String(code)); if(!s) return; resetRound(s,false); s.powerLog=['Players and scores cleared.']; emitHost(s); emitPlayers(s); });

  socket.on('markNumber', ({code, playerId, cardId, cellCode}, cb) => {
    const s=sessions.get(String(code)); const p=s?.players.get(String(playerId)); const card=p?.cards.find(c=>c.id===cardId);
    if(!s||!p||!card || p.kicked) return cb?.({ok:false,error:'Not found'});
    if(s.status!=='running' || !s.currentCall || Date.now()>s.callEndsAt) return cb?.({ok:false,error:'The 7-second call window is closed.'});
    if(p.selectedCallId === s.callId) return cb?.({ok:false,error:'One number per 7 seconds. Wait for the next call.'});
    if(cellCode !== s.currentCall.code) return cb?.({ok:false,error:'You can only mark the current called number.'});
    if(s.currentFreeze && s.currentFreeze.callId===s.callId && s.currentFreeze.byPlayerId !== p.id){
      const shieldCard = consumeAnyPower(p,'shield');
      if(shieldCard) s.powerLog.push(`${p.name}'s Shield blocked the freeze on ${s.currentCall.code}.`);
      else return cb?.({ok:false,error:`${s.currentCall.code} is frozen for this call.`});
    }
    const cell=card.grid.flat().find(c=>c.code===cellCode);
    if(!cell) return cb?.({ok:false,error:'That number is not on this card.'});
    if(cell.marked) return cb?.({ok:false,error:'Already selected green.'});
    cell.marked=true; cell.called=true; p.selectedCallId=s.callId;
    awardAllPowers(s,p); checkAutoWin(s,p); emitHost(s); emitPlayers(s); cb?.({ok:true});
  });

  socket.on('useFreeze', ({code, playerId, cardId}, cb) => {
    const s=sessions.get(String(code)); const p=s?.players.get(String(playerId)); const card=p?.cards.find(c=>c.id===cardId);
    if(!s||!p||!card || p.kicked) return cb?.({ok:false,error:'Not found'});
    if(!s.currentCall || s.status!=='running' || Date.now()>s.callEndsAt) return cb?.({ok:false,error:'Freeze can only be used during a live call.'});
    if(!consumePowerFromCard(card,'freeze')) return cb?.({ok:false,error:'No Freeze on this card.'});
    s.currentFreeze = { callId:s.callId, code:s.currentCall.code, byPlayerId:p.id, byName:p.name };
    s.powerLog.push(`${p.name} froze ${s.currentCall.code} for everyone else.`);
    emitHost(s); emitPlayers(s); cb?.({ok:true});
  });

  socket.on('useSteal', ({code, playerId, cardId}, cb) => {
    const s=sessions.get(String(code)); const p=s?.players.get(String(playerId)); const card=p?.cards.find(c=>c.id===cardId);
    if(!s||!p||!card || p.kicked) return cb?.({ok:false,error:'Not found'});
    if(!consumePowerFromCard(card,'steal')) return cb?.({ok:false,error:'No Steal on this card.'});
    const target=stealTarget(s,p.id);
    if(!target){ s.powerLog.push(`${p.name} used Steal, but nobody had a power to steal.`); emitHost(s); emitPlayer(s,p); return cb?.({ok:true}); }
    const loc=randomPowerLocation(target);
    loc.card.powers[loc.power]--;
    card.powers[loc.power]++;
    s.powerLog.push(`${p.name} stole ${loc.power.toUpperCase()} from ${target.name}.`);
    emitHost(s); emitPlayers(s); cb?.({ok:true});
  });

  socket.on('useSwap', ({code, playerId, cardId, cellCode}, cb) => {
    const s=sessions.get(String(code)); const p=s?.players.get(String(playerId)); const targetCard=p?.cards.find(c=>c.id===cardId);
    if(!s||!p||!targetCard || p.kicked) return cb?.({ok:false,error:'Not found'});
    if(!s.calledCodes.has(cellCode)) return cb?.({ok:false,error:'Swap can only use a number that has already been called.'});
    const targetCell=targetCard.grid.flat().find(c=>c.code===cellCode);
    if(!targetCell || targetCell.marked) return cb?.({ok:false,error:'Choose an orange unmarked number on this card.'});
    const powerCard = consumeAnyPower(p,'swap');
    if(!powerCard) return cb?.({ok:false,error:'No Swap available.'});
    let sourceCard=null, sourceCell=null;
    for(const c of p.cards){
      if(c.id===targetCard.id) continue;
      const found=c.grid.flat().find(cell=>cell.code===cellCode && cell.marked);
      if(found){ sourceCard=c; sourceCell=found; break; }
    }
    if(!sourceCell){ powerCard.powers.swap++; return cb?.({ok:false,error:'You need the same number marked green on another card to swap it here.'}); }
    sourceCell.marked=false; targetCell.marked=true; targetCell.called=true;
    awardAllPowers(s,p); checkAutoWin(s,p);
    s.powerLog.push(`${p.name} swapped ${cellCode} from ${shortCard(sourceCard.id)} to ${shortCard(targetCard.id)}.`);
    emitHost(s); emitPlayers(s); cb?.({ok:true});
  });
});

server.listen(PORT, () => console.log(`Barfly Blackout Bingo running on ${PORT}`));
