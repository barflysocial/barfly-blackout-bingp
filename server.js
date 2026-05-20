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
app.get('/health', (_, res) => res.json({ ok: true, app: 'Barfly Blackout Bingo' }));

const LETTERS = ['B', 'A', 'R', 'F', 'L', 'Y'];
const ROWS = 5;
const NUMS_PER_LETTER = 21;
const CALL_SECONDS = 7;
const MAX_CARDS = 12;
const sessions = new Map();

function id(prefix = '') { return prefix + crypto.randomBytes(4).toString('hex'); }
function makeCode() {
  let code;
  do { code = String(Math.floor(10000 + Math.random() * 90000)); } while (sessions.has(code));
  return code;
}
function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
function sample(nums, count) { return shuffle(nums).slice(0, count); }
function makeCard() {
  const grid = [];
  const ranges = LETTERS.map(letter => sample(Array.from({length: NUMS_PER_LETTER}, (_, i) => ({ letter, number: i + 1, code: `${letter}-${i + 1}` })), ROWS));
  for (let r = 0; r < ROWS; r++) grid.push(LETTERS.map((_, c) => ({ ...ranges[c][r], marked: false, called: false })));
  return { id: id('card_'), grid, frozenUntil: 0, lastFreezeBy: null };
}
function makeDeck() {
  const pool = [];
  for (const letter of LETTERS) for (let n = 1; n <= NUMS_PER_LETTER; n++) pool.push({ letter, number: n, code: `${letter}-${n}` });
  return shuffle(pool);
}
function visibleSession(s) {
  return {
    code: s.code,
    title: s.title,
    status: s.status,
    createdAt: s.createdAt,
    currentCall: s.currentCall,
    callId: s.callId,
    callEndsAt: s.callEndsAt,
    calledCodes: [...s.calledCodes],
    winners: s.winners,
    playerCount: s.players.size,
    leaderboard: leaderboard(s),
    qrDataUrl: s.qrDataUrl
  };
}
function publicPlayer(p) {
  return {
    id: p.id,
    name: p.name,
    cardCount: p.cards.length,
    approved: p.approved,
    powers: p.powers,
    frozenCards: p.cards.filter(c => Date.now() < c.frozenUntil).map(c => c.id),
    alreadyWon: p.alreadyWon
  };
}
function playerView(s, p) {
  updateCalledFlags(s, p);
  return {
    session: visibleSession(s),
    player: { ...publicPlayer(p), cards: p.cards, selectedCallId: p.selectedCallId, doubleActiveCallId: p.doubleActiveCallId },
    myRank: playerBest(s, p),
    powerLog: s.powerLog.slice(-12)
  };
}
function hostView(s) {
  const players = [...s.players.values()].map(p => ({ ...publicPlayer(p), best: playerBest(s, p), cards: p.cards.map(c => ({ id: c.id, lines: completedLines(c), marked: countMarked(c), remaining: remaining(c), frozenUntil: c.frozenUntil })) }));
  return { session: visibleSession(s), players, powerLog: s.powerLog.slice(-20) };
}
function updateCalledFlags(s, p) {
  for (const card of p.cards) for (const row of card.grid) for (const cell of row) cell.called = s.calledCodes.has(cell.code);
}
function countMarked(card) { return card.grid.flat().filter(c => c.marked).length; }
function remaining(card) { return card.grid.flat().filter(c => !c.marked).length; }
function isBlackout(card) { return remaining(card) === 0; }
function completedLines(card) {
  let lines = 0;
  for (let r = 0; r < ROWS; r++) if (card.grid[r].every(c => c.marked)) lines++;
  for (let c = 0; c < LETTERS.length; c++) if (card.grid.every(row => row[c].marked)) lines++;
  if ([0,1,2,3,4].every(i => card.grid[i][i].marked)) lines++;
  if ([0,1,2,3,4].every(i => card.grid[i][LETTERS.length - 1 - i].marked)) lines++;
  return lines;
}
function playerBest(s, p) {
  let best = null;
  for (const card of p.cards) {
    const b = { cardId: card.id, lines: completedLines(card), marked: countMarked(card), remaining: remaining(card), frozen: Date.now() < card.frozenUntil };
    if (!best || b.lines > best.lines || (b.lines === best.lines && b.marked > best.marked) || (b.lines === best.lines && b.marked === best.marked && b.remaining < best.remaining)) best = b;
  }
  return best || { cardId: null, lines: 0, marked: 0, remaining: 30, frozen: false };
}
function leaderboard(s) {
  return [...s.players.values()].filter(p => p.approved).map(p => ({ playerId: p.id, name: p.name, ...playerBest(s, p), cards: p.cards.length }))
    .sort((a,b) => b.lines - a.lines || b.marked - a.marked || a.remaining - b.remaining || a.cards - b.cards).slice(0,5);
}
function awardPowers(s, p) {
  const totalLines = p.cards.reduce((sum, c) => sum + completedLines(c), 0);
  const freezeEarned = Math.floor(totalLines / 5);
  const shieldEarned = Math.floor(totalLines / 3);
  const doubleEarned = Math.floor(totalLines / 4);
  if (freezeEarned > p.awards.freeze) { p.powers.freeze += freezeEarned - p.awards.freeze; p.awards.freeze = freezeEarned; s.powerLog.push(`${p.name} earned Freeze`); }
  if (shieldEarned > p.awards.shield) { p.powers.shield += shieldEarned - p.awards.shield; p.awards.shield = shieldEarned; s.powerLog.push(`${p.name} earned Shield`); }
  if (doubleEarned > p.awards.doubleTap) { p.powers.doubleTap += doubleEarned - p.awards.doubleTap; p.awards.doubleTap = doubleEarned; s.powerLog.push(`${p.name} earned Double Tap`); }
}
function createSession(title, hostOrigin) {
  const code = makeCode();
  const joinUrl = `${hostOrigin || ''}/player.html?code=${code}`;
  const s = { code, title: title || 'Barfly Blackout Bingo', status: 'lobby', createdAt: Date.now(), players: new Map(), deck: makeDeck(), calledCodes: new Set(), currentCall: null, callId: 0, callEndsAt: 0, interval: null, winners: [], powerLog: [], qrDataUrl: '' };
  sessions.set(code, s);
  QRCode.toDataURL(joinUrl, { margin: 1, width: 320 }).then(url => { s.qrDataUrl = url; emitHost(s); });
  return s;
}
function emitHost(s) { io.to(`host:${s.code}`).emit('hostState', hostView(s)); io.to(`session:${s.code}`).emit('sessionState', visibleSession(s)); }
function emitPlayer(s, p) { io.to(`player:${p.id}`).emit('playerState', playerView(s, p)); }
function emitPlayers(s) { for (const p of s.players.values()) emitPlayer(s, p); }
function nextCall(s) {
  if (s.status !== 'running') return;
  const next = s.deck.shift();
  if (!next) { s.status = 'ended'; clearInterval(s.interval); s.interval = null; emitHost(s); emitPlayers(s); return; }
  s.currentCall = next;
  s.callId++;
  s.callEndsAt = Date.now() + CALL_SECONDS * 1000;
  s.calledCodes.add(next.code);
  for (const p of s.players.values()) p.selectedCallId = null;
  emitHost(s); emitPlayers(s);
}
function checkAutoWin(s, p, card) {
  if (p.alreadyWon || s.winners.find(w => w.playerId === p.id)) return;
  if (isBlackout(card)) {
    p.alreadyWon = true;
    const win = { playerId: p.id, name: p.name, cardId: card.id, at: Date.now() };
    s.winners.push(win);
    s.powerLog.push(`BARFLY BLACKOUT: ${p.name} won on ${card.id.slice(-4).toUpperCase()}`);
    emitHost(s); emitPlayers(s);
  }
}
function findFreezeTarget(s, userId) {
  let target = null;
  for (const p of s.players.values()) {
    if (p.id === userId || !p.approved || p.alreadyWon) continue;
    for (const card of p.cards) {
      if (Date.now() < card.frozenUntil) continue;
      const t = { player: p, card, lines: completedLines(card), marked: countMarked(card), remaining: remaining(card) };
      if (!target || t.lines > target.lines || (t.lines === target.lines && t.marked > target.marked) || (t.lines === target.lines && t.marked === target.marked && t.remaining < target.remaining)) target = t;
    }
  }
  return target;
}

io.on('connection', socket => {
  socket.on('createSession', ({ title, origin }, cb) => {
    const s = createSession(title, origin);
    socket.join(`host:${s.code}`);
    cb?.({ ok: true, state: hostView(s) });
  });
  socket.on('joinHost', ({ code }, cb) => {
    const s = sessions.get(String(code));
    if (!s) return cb?.({ ok:false, error:'Session not found' });
    socket.join(`host:${s.code}`); cb?.({ ok:true, state: hostView(s) });
  });
  socket.on('joinPlayer', ({ code, name, cardCount }, cb) => {
    const s = sessions.get(String(code));
    if (!s) return cb?.({ ok:false, error:'Session not found' });
    const count = Math.max(1, Math.min(MAX_CARDS, Number(cardCount || 1)));
    const p = { id: id('p_'), name: String(name || 'Player').trim().slice(0,24), cards: Array.from({length: count}, makeCard), approved: false, powers: { freeze:0, shield:0, doubleTap:0 }, awards: { freeze:0, shield:0, doubleTap:0 }, selectedCallId: null, doubleActiveCallId: null, alreadyWon: false };
    s.players.set(p.id, p);
    socket.join(`session:${s.code}`); socket.join(`player:${p.id}`);
    cb?.({ ok:true, playerId: p.id, state: playerView(s,p) }); emitHost(s);
  });
  socket.on('resumePlayer', ({ code, playerId }, cb) => {
    const s = sessions.get(String(code)); const p = s?.players.get(String(playerId));
    if (!s || !p) return cb?.({ ok:false, error:'Player not found' });
    socket.join(`session:${s.code}`); socket.join(`player:${p.id}`); cb?.({ ok:true, state: playerView(s,p) });
  });
  socket.on('approvePlayer', ({ code, playerId }) => { const s=sessions.get(String(code)); const p=s?.players.get(String(playerId)); if (p) { p.approved = true; emitHost(s); emitPlayer(s,p); } });
  socket.on('approveAll', ({ code }) => { const s=sessions.get(String(code)); if (s) { for (const p of s.players.values()) p.approved=true; emitHost(s); emitPlayers(s); } });
  socket.on('startGame', ({ code }) => { const s=sessions.get(String(code)); if (!s) return; s.status='running'; if (s.interval) clearInterval(s.interval); nextCall(s); s.interval=setInterval(()=>nextCall(s), CALL_SECONDS*1000); });
  socket.on('pauseGame', ({ code }) => { const s=sessions.get(String(code)); if (!s) return; s.status='paused'; if (s.interval) clearInterval(s.interval); s.interval=null; emitHost(s); emitPlayers(s); });
  socket.on('nextCall', ({ code }) => { const s=sessions.get(String(code)); if (!s) return; if (s.interval) clearInterval(s.interval); s.status='running'; nextCall(s); s.interval=setInterval(()=>nextCall(s), CALL_SECONDS*1000); });
  socket.on('resetSession', ({ code }) => { const old=sessions.get(String(code)); if (!old) return; if (old.interval) clearInterval(old.interval); const s=createSession(old.title, ''); sessions.delete(s.code); sessions.set(old.code, s); s.code=old.code; emitHost(s); emitPlayers(s); });
  socket.on('markNumber', ({ code, playerId, cardId, cellCode, useDouble }, cb) => {
    const s=sessions.get(String(code)); const p=s?.players.get(String(playerId)); const card=p?.cards.find(c=>c.id===cardId);
    if (!s || !p || !card) return cb?.({ ok:false, error:'Not found' });
    if (!p.approved) return cb?.({ ok:false, error:'Cards are waiting for host approval.' });
    if (s.status !== 'running' || !s.currentCall || Date.now() > s.callEndsAt) return cb?.({ ok:false, error:'The 7-second call window is closed.' });
    if (Date.now() < card.frozenUntil) return cb?.({ ok:false, error:'This card is frozen for this turn.' });
    const doubleActive = useDouble && p.powers.doubleTap > 0;
    if (p.selectedCallId === s.callId && !doubleActive) return cb?.({ ok:false, error:'One number per 7 seconds. Wait for the next call.' });
    if (cellCode !== s.currentCall.code) return cb?.({ ok:false, error:'You can only mark the current called number.' });
    const cell = card.grid.flat().find(c=>c.code===cellCode);
    if (!cell) return cb?.({ ok:false, error:'That number is not on this card.' });
    if (cell.marked) return cb?.({ ok:false, error:'Already marked.' });
    cell.marked = true; cell.called = true;
    if (p.selectedCallId === s.callId && doubleActive) { p.powers.doubleTap--; p.doubleActiveCallId = s.callId; }
    p.selectedCallId = s.callId;
    awardPowers(s,p); checkAutoWin(s,p,card); emitHost(s); emitPlayer(s,p); cb?.({ ok:true });
  });
  socket.on('useFreeze', ({ code, playerId }, cb) => {
    const s=sessions.get(String(code)); const p=s?.players.get(String(playerId));
    if (!s || !p) return cb?.({ ok:false, error:'Not found' });
    if (p.powers.freeze < 1) return cb?.({ ok:false, error:'No Freeze available.' });
    const target = findFreezeTarget(s, p.id);
    if (!target) return cb?.({ ok:false, error:'No eligible target.' });
    if (target.player.powers.shield > 0) { target.player.powers.shield--; p.powers.freeze--; s.powerLog.push(`${target.player.name}'s Shield blocked ${p.name}'s Freeze`); }
    else { p.powers.freeze--; target.card.frozenUntil = Date.now() + CALL_SECONDS * 1000; target.card.lastFreezeBy = p.name; s.powerLog.push(`${p.name} froze ${target.player.name}'s strongest card for 7 seconds`); }
    emitHost(s); emitPlayers(s); cb?.({ ok:true });
  });
});

server.listen(PORT, () => console.log(`Barfly Blackout Bingo running on ${PORT}`));
