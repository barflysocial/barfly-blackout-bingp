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
app.get('/', (_, res) => res.redirect('/player'));
app.get('/player', (_, res) => res.sendFile(__dirname + '/public/player.html'));
app.get('/host', (_, res) => res.sendFile(__dirname + '/public/host.html'));
app.get('/health', (_, res) => res.json({ ok: true, app: 'Barfly Blackout Bingo' }));

const LETTERS = ['B', 'I', 'N', 'G', 'O'];
const RANGES = { B: [1, 15], I: [16, 30], N: [31, 45], G: [46, 60], O: [61, 75] };
const sessions = new Map();
const BAD_WORDS = ['fuck','shit','bitch','asshole','cunt','dick','pussy','nigger','faggot','whore','slut'];

function id(prefix='') { return prefix + crypto.randomBytes(5).toString('hex'); }
function makeCode() { let c; do c = String(Math.floor(10000 + Math.random()*90000)); while (sessions.has(c)); return c; }
function shuffle(a) { const x = [...a]; for (let i=x.length-1; i>0; i--) { const j = Math.floor(Math.random()*(i+1)); [x[i],x[j]]=[x[j],x[i]]; } return x; }
function normalizePhone(raw) { return String(raw || '').replace(/\D/g,'').slice(-10); }
function maskPhone(raw) { const p = normalizePhone(raw); return p.length === 10 ? `***-***-${p.slice(-4)}` : 'No phone'; }
function cleanName(raw, count=0) {
  const name = String(raw || '').trim().replace(/\s+/g,' ').slice(0,24) || `Guest ${String(count+1).padStart(3,'0')}`;
  const test = name.toLowerCase().replace(/[^a-z0-9]/g,'');
  return BAD_WORDS.some(w => test.includes(w)) ? `Guest ${String(count+1).padStart(3,'0')}` : name;
}
function cleanHandle(raw) { return String(raw || '').trim().replace(/\s+/g,' ').slice(0,32); }
function parseScheduledAt(date, time) {
  if (!date || !time) return null;
  const ms = new Date(`${date}T${time}:00`).getTime();
  return Number.isFinite(ms) ? ms : null;
}
function chunk(arr, size) { const out=[]; for(let i=0;i<arr.length;i+=size) out.push(arr.slice(i,i+size)); return out; }
function makeCardFromColumns(columnNums) {
  const grid = [];
  LETTERS.forEach((letter, c) => {
    columnNums[c].forEach((n,r) => {
      if (!grid[r]) grid[r] = [];
      grid[r].push({ letter, number:n, code:`${letter}-${n}`, called:false, marked:false });
    });
  });
  return { id: id('card_'), grid };
}
function makeCardSet(count=3) {
  const cardCount = Math.max(1, Math.min(12, Number(count)||3));
  if (cardCount === 3) {
    const cols = LETTERS.map(letter => {
      const [a,b] = RANGES[letter];
      return chunk(shuffle(Array.from({length:b-a+1}, (_,i)=>a+i)), 5);
    });
    return [0,1,2].map(i => makeCardFromColumns(cols.map(col => col[i])));
  }
  return Array.from({length: cardCount}, makeCard);
}
function makeCard() {
  const grid = [];
  for (const letter of LETTERS) {
    const [a,b] = RANGES[letter];
    const nums = shuffle(Array.from({length: b-a+1}, (_,i)=>a+i)).slice(0,5);
    nums.forEach((n,r) => {
      if (!grid[r]) grid[r] = [];
      grid[r].push({ letter, number:n, code:`${letter}-${n}`, called:false, marked:false });
    });
  }
  return { id: id('card_'), grid };
}
function makeDeck() {
  const out = [];
  for (const letter of LETTERS) {
    const [a,b] = RANGES[letter];
    for (let n=a; n<=b; n++) out.push({ letter, number:n, code:`${letter}-${n}` });
  }
  return shuffle(out);
}
function countMarked(card) { return card.grid.flat().filter(c => c.marked).length; }
function isBlackout(card) { return countMarked(card) === 25; }
function bestCard(player) {
  return player.cards.map((card, i) => ({ cardId: card.id, cardNumber: i+1, marked: countMarked(card), remaining: 25-countMarked(card), blackedOut: isBlackout(card) }))
    .sort((a,b) => b.marked-a.marked || a.cardNumber-b.cardNumber)[0] || { marked:0, remaining:25, cardNumber:1 };
}
function updateCalledFlags(session, player) {
  for (const card of player.cards) for (const row of card.grid) for (const cell of row) cell.called = session.calledCodes.has(cell.code);
}
function playerAlreadyWon(session, playerId) { return session.winners.some(w => w.playerId === playerId); }
function activePlayers(session) { return [...session.players.values()].filter(p => !p.kicked); }
function progressList(session, excludeWinners=false) {
  const winnerIds = new Set(session.winners.map(w=>w.playerId));
  return activePlayers(session)
    .filter(p => !excludeWinners || !winnerIds.has(p.id))
    .map(p => ({ playerId:p.id, name:p.name, ...bestCard(p), cardCount:p.cards.length }))
    .sort((a,b) => b.marked-a.marked || a.remaining-b.remaining || a.name.localeCompare(b.name));
}
function snapshotAtWin(session, winnerId) {
  return progressList(session, false)
    .filter(x => x.playerId !== winnerId)
    .slice(0,5)
    .map((x, i) => ({ rank:i+2, playerId:x.playerId, name:x.name, marked:x.marked, remaining:x.remaining, cardNumber:x.cardNumber }));
}
function playerJoinUrl(session, origin='') { return `${origin}/player?code=${session.code}`; }
function sessionLabel(session) {
  if (!session.scheduledAt) return `${session.title} — Code ${session.code}`;
  return `${session.title} — ${new Date(session.scheduledAt).toLocaleString([], { weekday:'short', month:'short', day:'numeric', hour:'numeric', minute:'2-digit' })}`;
}
async function refreshQr(session, origin='') {
  try { session.qrDataUrl = await QRCode.toDataURL(playerJoinUrl(session, origin), { margin:1, width:360 }); } catch {}
}
function createSession({ title, origin, cardsPerPlayer=3, cap=40, tipLink='', scheduledAt=null, timezone='', sponsorName='', sponsorMessage='', sponsorLogo='' }) {
  const code = makeCode();
  const session = {
    code,
    title:title || 'Barfly Blackout Bingo',
    status: scheduledAt ? 'scheduled' : 'lobby',
    scheduledAt: scheduledAt || null, // UTC millisecond timestamp
    timezone: timezone || 'local',
    cardsPerPlayer: Math.max(1, Math.min(12, Number(cardsPerPlayer)||3)),
    cap: Math.max(1, Math.min(500, Number(cap)||40)),
    tipLink: String(tipLink || '').trim(),
    sponsor: { name:String(sponsorName||'').trim(), message:String(sponsorMessage||'').trim(), logo:String(sponsorLogo||'').trim() },
    reservations: [],
    players: new Map(),
    deck: makeDeck(),
    calledCodes: new Set(),
    currentCall:null,
    callId:0,
    winners:[],
    createdAt: Date.now(),
    qrDataUrl:'',
    hostLog:['Session created.'],
    autoTimer:null,
    callIntervalMs:7000
  };
  sessions.set(code, session);
  refreshQr(session, origin).then(() => emitHost(session));
  return session;
}
function publicSession(session) {
  const reserved = session.reservations.filter(r => r.status === 'reserved').length;
  const checkedIn = session.reservations.filter(r => r.checkedIn).length;
  return {
    code: session.code,
    title: session.title,
    status: session.status,
    scheduledAt: session.scheduledAt,
    timezone: session.timezone,
    cap: session.cap,
    reserved,
    checkedIn,
    full: reserved >= session.cap,
    label: sessionLabel(session)
  };
}
function publicSessions() {
  return [...sessions.values()]
    .filter(s => s.status !== 'ended')
    .sort((a,b) => (a.scheduledAt || a.createdAt) - (b.scheduledAt || b.createdAt))
    .map(publicSession);
}
function visibleSession(session) {
  return {
    code:session.code,
    title:session.title,
    status:session.status,
    scheduledAt:session.scheduledAt,
    cardsPerPlayer:session.cardsPerPlayer,
    cap:session.cap,
    tipLink:session.tipLink,
    sponsor:session.sponsor,
    serverNow:Date.now(),
    currentCall:session.currentCall,
    callId:session.callId,
    calledCodes:[...session.calledCodes],
    winners:session.winners,
    leaderboard:progressList(session, true).slice(0,10),
    qrDataUrl:session.qrDataUrl,
    callIntervalMs:session.callIntervalMs,
    reservationsCount: session.reservations.length,
    checkedInCount: session.reservations.filter(r => r.checkedIn).length
  };
}
function playerView(session, player) {
  updateCalledFlags(session, player);
  return { session: visibleSession(session), player: { id:player.id, name:player.name, cards:player.cards, kicked:!!player.kicked }, myBest: bestCard(player) };
}
function hostView(session) {
  return {
    session: visibleSession(session),
    players: activePlayers(session).map(p => ({ id:p.id, name:p.name, cardCount:p.cards.length, best:bestCard(p), kicked:!!p.kicked })),
    reservations: session.reservations.map(r => ({ id:r.id, name:r.name, phoneMasked:maskPhone(r.phone), social:r.social, status:r.status, checkedIn:r.checkedIn, playerId:r.playerId, createdAt:r.createdAt })),
    hostLog:session.hostLog.slice(-80)
  };
}
function emitHost(session) { io.to(`host:${session.code}`).emit('hostState', hostView(session)); io.to('host:lobby').emit('hostSessions', publicSessions()); }
function emitPlayers(session) { for (const p of activePlayers(session)) io.to(`player:${p.id}`).emit('playerState', playerView(session,p)); io.to(`session:${session.code}`).emit('sessionState', visibleSession(session)); }
function emitAll(session) { emitHost(session); emitPlayers(session); io.emit('publicSessions', publicSessions()); }
function resetRound(session, keepPlayers=true) {
  if (session.autoTimer) clearInterval(session.autoTimer);
  session.status = session.scheduledAt && session.scheduledAt > Date.now() ? 'scheduled' : 'lobby';
  session.deck = makeDeck(); session.calledCodes = new Set(); session.currentCall = null; session.callId = 0; session.winners = [];
  if (!keepPlayers) {
    session.players = new Map();
    session.reservations.forEach(r => { r.checkedIn = false; r.playerId = null; });
  }
  for (const p of session.players.values()) p.cards = makeCardSet(session.cardsPerPlayer);
  session.hostLog.push(keepPlayers ? 'New round created. Players kept.' : 'Game cleared. Players and scores removed.');
}
function callNext(session) {
  if (session.status !== 'running') session.status = 'running';
  const next = session.deck.shift();
  if (!next) { session.status='ended'; session.hostLog.push('All numbers have been called.'); emitAll(session); return; }
  session.currentCall = next; session.callId += 1; session.calledCodes.add(next.code);
  for (const p of session.players.values()) updateCalledFlags(session, p);
  session.hostLog.push(`Called ${next.code}.`);
  emitAll(session);
}
function checkForWin(session, player, card) {
  if (!isBlackout(card) || playerAlreadyWon(session, player.id) || session.winners.length >= 3) return;
  const atMs = Date.now();
  const winner = { place: session.winners.length + 1, playerId:player.id, name:player.name, cardId:card.id, cardNumber:player.cards.findIndex(c=>c.id===card.id)+1, atMs, snapshot:snapshotAtWin(session, player.id) };
  session.winners.push(winner);
  session.hostLog.push(`${winner.place}${winner.place===1?'st':winner.place===2?'nd':'rd'} place: ${player.name} on Card ${winner.cardNumber}.`);
  if (session.winners.length >= 3) { session.status = 'ended'; if (session.autoTimer) clearInterval(session.autoTimer); session.autoTimer=null; }
}
function createPlayerForSession(session, name, reservation=null) {
  const player = { id:id('p_'), name:cleanName(name, session.players.size), cards:makeCardSet(session.cardsPerPlayer), kicked:false, reservationId: reservation?.id || null };
  updateCalledFlags(session, player);
  session.players.set(player.id, player);
  if (reservation) { reservation.checkedIn = true; reservation.playerId = player.id; }
  session.hostLog.push(`${player.name} checked in.`);
  return player;
}

setInterval(() => {
  const now = Date.now();
  for (const s of sessions.values()) {
    if ((s.status === 'scheduled' || s.status === 'lobby') && s.scheduledAt && s.scheduledAt <= now) {
      s.status = 'running';
      s.hostLog.push('Scheduled start time reached. Game opened. Host may begin calling.');
      emitAll(s);
    }
  }
}, 1000);

io.on('connection', socket => {
  socket.on('listPublicSessions', (_, cb) => cb?.({ ok:true, sessions: publicSessions() }));
  socket.on('hostListSessions', (_, cb) => { socket.join('host:lobby'); cb?.({ ok:true, sessions: publicSessions() }); });
  socket.on('createSession', async ({ title, cardsPerPlayer, cap, tipLink, date, time, origin, scheduledAtUtc, timezone, sponsorName, sponsorMessage, sponsorLogo }, cb) => {
    const utc = Number(scheduledAtUtc);
    const scheduledAt = Number.isFinite(utc) && utc > 0 ? utc : parseScheduledAt(date, time);
    const session = createSession({ title, origin, cardsPerPlayer, cap, tipLink, scheduledAt, timezone, sponsorName, sponsorMessage, sponsorLogo });
    socket.join(`host:${session.code}`);
    cb?.({ ok:true, state: hostView(session), code: session.code });
    io.emit('publicSessions', publicSessions());
  });
  socket.on('hostJoin', ({ code }, cb) => {
    const session = sessions.get(String(code||'').trim());
    if (!session) return cb?.({ ok:false, error:'Session not found.' });
    socket.join(`host:${session.code}`);
    cb?.({ ok:true, state: hostView(session) });
  });
  socket.on('reserveSpot', ({ code, name, phone, social }, cb) => {
    const session = sessions.get(String(code||'').trim());
    if (!session) return cb?.({ ok:false, error:'Game not found.' });
    if (session.status === 'ended') return cb?.({ ok:false, error:'This game has ended.' });
    const phoneClean = normalizePhone(phone);
    if (phoneClean.length !== 10) return cb?.({ ok:false, error:'Enter a 10-digit phone number.' });
    const reservedCount = session.reservations.filter(r => r.status === 'reserved').length;
    if (!session.reservations.some(r => r.phone === phoneClean && r.status === 'reserved') && reservedCount >= session.cap) return cb?.({ ok:false, error:'This game is full.' });
    let reservation = session.reservations.find(r => r.phone === phoneClean && r.status === 'reserved');
    if (reservation) {
      reservation.name = cleanName(name, session.reservations.length);
      reservation.social = cleanHandle(social);
      session.hostLog.push(`${reservation.name} updated an RSVP.`);
    } else {
      reservation = { id:id('r_'), name:cleanName(name, session.reservations.length), phone:phoneClean, social:cleanHandle(social), status:'reserved', checkedIn:false, playerId:null, createdAt:Date.now() };
      session.reservations.push(reservation);
      session.hostLog.push(`${reservation.name} reserved a spot.`);
    }
    emitAll(session);
    cb?.({ ok:true, reservation:{ ...reservation, phoneMasked:maskPhone(reservation.phone) }, session: publicSession(session) });
  });
  socket.on('findReservations', ({ phone }, cb) => {
    const phoneClean = normalizePhone(phone);
    if (phoneClean.length !== 10) return cb?.({ ok:false, error:'Enter a 10-digit phone number.' });
    const out = [];
    for (const s of sessions.values()) {
      for (const r of s.reservations.filter(x => x.phone === phoneClean)) {
        out.push({ reservationId:r.id, code:s.code, title:s.title, scheduledAt:s.scheduledAt, status:s.status, name:r.name, social:r.social, checkedIn:r.checkedIn, playerId:r.playerId, label:sessionLabel(s) });
      }
    }
    out.sort((a,b)=>(a.scheduledAt||0)-(b.scheduledAt||0));
    cb?.({ ok:true, reservations:out });
  });
  socket.on('checkInReservation', ({ code, reservationId }, cb) => {
    const session = sessions.get(String(code||'').trim());
    const reservation = session?.reservations.find(r => r.id === reservationId);
    if (!session || !reservation) return cb?.({ ok:false, error:'Reservation not found.' });
    if (session.status === 'ended') return cb?.({ ok:false, error:'This game has ended.' });
    let player = reservation.playerId ? session.players.get(reservation.playerId) : null;
    if (!player) player = createPlayerForSession(session, reservation.name, reservation);
    socket.join(`player:${player.id}`); socket.join(`session:${session.code}`);
    emitAll(session);
    cb?.({ ok:true, playerId:player.id, state:playerView(session, player) });
  });
  socket.on('joinPlayer', ({ code, name }, cb) => {
    const session = sessions.get(String(code||'').trim());
    if (!session) return cb?.({ ok:false, error:'Session not found.' });
    if (session.status === 'ended') return cb?.({ ok:false, error:'This session has ended.' });
    const player = createPlayerForSession(session, name, null);
    socket.join(`player:${player.id}`); socket.join(`session:${session.code}`);
    cb?.({ ok:true, playerId:player.id, state:playerView(session, player) });
    emitAll(session);
  });
  socket.on('resumePlayer', ({ code, playerId }, cb) => {
    const session = sessions.get(String(code||'').trim());
    const player = session?.players.get(playerId);
    if (!session || !player || player.kicked) return cb?.({ ok:false, error:'Player not found.' });
    socket.join(`player:${player.id}`); socket.join(`session:${session.code}`);
    cb?.({ ok:true, state:playerView(session, player) });
  });
  socket.on('setCardsPerPlayer', ({ code, cardsPerPlayer }, cb) => {
    const session = sessions.get(String(code||'').trim());
    if (!session) return cb?.({ ok:false, error:'Session not found.' });
    if (!['scheduled','lobby'].includes(session.status)) return cb?.({ ok:false, error:'Change card count before starting the round.' });
    session.cardsPerPlayer = Math.max(1, Math.min(12, Number(cardsPerPlayer)||3));
    for (const p of session.players.values()) p.cards = makeCardSet(session.cardsPerPlayer);
    session.hostLog.push(`Cards per player set to ${session.cardsPerPlayer}.`);
    emitAll(session); cb?.({ ok:true });
  });
  socket.on('startGame', ({ code }, cb) => {
    const session = sessions.get(String(code||'').trim()); if (!session) return cb?.({ ok:false, error:'Session not found.' });
    session.status='running'; callNext(session); cb?.({ ok:true });
  });
  socket.on('callNext', ({ code }, cb) => { const session = sessions.get(String(code||'').trim()); if (!session) return cb?.({ ok:false, error:'Session not found.' }); callNext(session); cb?.({ ok:true }); });
  socket.on('toggleAutoCall', ({ code, on, ms }, cb) => {
    const session = sessions.get(String(code||'').trim()); if (!session) return cb?.({ ok:false, error:'Session not found.' });
    if (session.autoTimer) clearInterval(session.autoTimer); session.autoTimer = null;
    if (on) { session.callIntervalMs = Math.max(3000, Math.min(30000, Number(ms)||7000)); if (session.status !== 'running') callNext(session); session.autoTimer = setInterval(()=>callNext(session), session.callIntervalMs); session.hostLog.push(`Auto-call on every ${(session.callIntervalMs/1000).toFixed(0)} seconds.`); }
    else session.hostLog.push('Auto-call off.');
    emitAll(session); cb?.({ ok:true });
  });
  socket.on('markNumber', ({ code, playerId, cardId, cellCode }, cb) => {
    const session = sessions.get(String(code||'').trim()); const player = session?.players.get(playerId); const card = player?.cards.find(c=>c.id===cardId);
    if (!session || !player || !card || player.kicked) return cb?.({ ok:false, error:'Card not found.' });
    if (playerAlreadyWon(session, player.id)) return cb?.({ ok:false, error:'You already placed this round.' });
    const cell = card.grid.flat().find(c=>c.code===cellCode);
    if (!cell) return cb?.({ ok:false, error:'Number not found.' });
    if (!session.calledCodes.has(cell.code)) return cb?.({ ok:false, error:'That number has not been called yet.' });
    if (cell.marked) return cb?.({ ok:false, error:'Already selected.' });
    cell.called = true; cell.marked = true;
    checkForWin(session, player, card);
    emitAll(session); cb?.({ ok:true });
  });
  socket.on('renamePlayer', ({ code, playerId, name }, cb) => {
    const session = sessions.get(String(code||'').trim()); const player = session?.players.get(playerId);
    if (!session || !player) return cb?.({ ok:false, error:'Player not found.' });
    const old = player.name; player.name = cleanName(name, 0); session.winners.forEach(w => { if (w.playerId === playerId) w.name = player.name; });
    const res = session.reservations.find(r => r.playerId === playerId); if (res) res.name = player.name;
    session.hostLog.push(`Host renamed ${old} to ${player.name}.`); emitAll(session); cb?.({ ok:true });
  });
  socket.on('kickPlayer', ({ code, playerId }, cb) => {
    const session = sessions.get(String(code||'').trim()); const player = session?.players.get(playerId);
    if (!session || !player) return cb?.({ ok:false, error:'Player not found.' });
    player.kicked = true; io.to(`player:${player.id}`).emit('kicked', { message:'You have been removed from this game by the host.' }); session.hostLog.push(`${player.name} was kicked.`); emitAll(session); cb?.({ ok:true });
  });
  socket.on('endGame', ({ code }, cb) => { const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); if(s.autoTimer)clearInterval(s.autoTimer); s.autoTimer=null; s.status='ended'; s.hostLog.push('Game ended by host.'); emitAll(s); cb?.({ok:true}); });
  socket.on('newRound', ({ code }, cb) => { const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); resetRound(s,true); emitAll(s); cb?.({ok:true}); });
  socket.on('clearGame', ({ code }, cb) => { const s=sessions.get(String(code||'').trim()); if(!s)return cb?.({ok:false,error:'Session not found.'}); resetRound(s,false); emitAll(s); cb?.({ok:true}); });
});

server.listen(PORT, () => console.log(`Barfly Blackout Bingo running on ${PORT}`));
