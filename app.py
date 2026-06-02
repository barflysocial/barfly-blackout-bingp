import json, os, random, sqlite3, time
from datetime import datetime
from pathlib import Path
from flask import Flask, g, jsonify, redirect, render_template, request, session as flask_session, url_for

APP_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get('DATA_DIR', APP_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / 'battle_bingo.db'
POWER_POOL = ['Lucky Spot','Number Peek','Second Chance','Freeze','Row Block','Card Shuffle','Shield Breaker','Mirror Attack','Power Swap']
CALL_POOL = list(range(1,76))
COLS = {'B': range(1,16), 'I': range(16,31), 'N': range(31,46), 'G': range(46,61), 'O': range(61,76)}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY','battle-bingo-dev-key')


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    if 'db' in g: g.db.close()

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, venue TEXT, status TEXT DEFAULT 'lobby',
      blackout_goal INTEGER DEFAULT 3,
      triple_winners_goal INTEGER DEFAULT 1,
      countdown INTEGER DEFAULT 10,
      mark_mode TEXT DEFAULT 'manual',
      tv_enabled INTEGER DEFAULT 1,
      powers_enabled INTEGER DEFAULT 1,
      locked INTEGER DEFAULT 0,
      called_numbers TEXT DEFAULT '[]',
      remaining_numbers TEXT DEFAULT '[]',
      current_number INTEGER,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      started_at TEXT,
      ended_at TEXT
    );
    CREATE TABLE IF NOT EXISTS players (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id INTEGER, phone TEXT, alias TEXT, status TEXT DEFAULT 'active',
      points INTEGER DEFAULT 0, cards TEXT, marks TEXT, row_credits TEXT, blackouts TEXT,
      powers TEXT DEFAULT '[]', used_powers TEXT DEFAULT '[]', power_cooldown_call INTEGER,
      afk_misses INTEGER DEFAULT 0, joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(session_id, phone), UNIQUE(session_id, alias)
    );
    CREATE TABLE IF NOT EXISTS feed (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id INTEGER, type TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS prizes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id INTEGER, placement TEXT, sponsor TEXT, prize TEXT, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      venue TEXT, category TEXT, alias TEXT, value TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    con.commit(); con.close()


def jload(x, default):
    try: return json.loads(x) if x else default
    except Exception: return default

def add_feed(session_id, typ, msg):
    db().execute('INSERT INTO feed(session_id,type,message) VALUES(?,?,?)',(session_id, typ, msg)); db().commit()

def active_session():
    row = db().execute('SELECT * FROM sessions ORDER BY id DESC LIMIT 1').fetchone()
    if not row:
        remaining = json.dumps(CALL_POOL.copy())
        db().execute("INSERT INTO sessions(name,venue,remaining_numbers) VALUES(?,?,?)",('Battle Bingo','Barfly Social',remaining)); db().commit()
        row = db().execute('SELECT * FROM sessions ORDER BY id DESC LIMIT 1').fetchone()
    return row

def clean_alias(alias):
    alias = ''.join(ch for ch in alias.strip() if ch.isalnum() or ch in ['_','-'])[:20]
    return alias or f'Player{random.randint(100,999)}'

def random_alias():
    a = random.choice(['Blue','Gold','Lucky','Silver','Neon','Royal','Clover','Teal','Velvet','Storm'])
    b = random.choice(['Tiger','Falcon','Otter','Dragon','Wolf','Comet','Wizard','Ace','Lynx','Maven'])
    return f'{a}{b}{random.randint(10,99)}'

def make_cards():
    cards = []
    split_cols = {}
    for letter, nums in COLS.items():
        nums = list(nums); random.shuffle(nums)
        split_cols[letter] = [nums[i*5:(i+1)*5] for i in range(3)]
    for c in range(3):
        grid = []
        for r in range(5):
            grid.append({letter: split_cols[letter][c][r] for letter in 'BINGO'})
        cards.append(grid)
    return cards

def evaluate_player(p, s, newly_marked=None):
    cards = jload(p['cards'], [])
    marks = set(jload(p['marks'], []))
    row_credits = set(jload(p['row_credits'], []))
    blackouts = set(jload(p['blackouts'], []))
    powers = jload(p['powers'], [])
    points = p['points']
    changed = False
    for ci, card in enumerate(cards):
        for ri, row in enumerate(card):
            key = f'{ci}:{ri}'
            nums = set(row.values())
            if key not in row_credits and nums.issubset(marks):
                row_credits.add(key); points += 25; changed = True
                add_feed(p['session_id'],'bingo',f'🏆 {p["alias"]} completed Row {ri+1} on Card {chr(65+ci)} (+25)')
                card_rows = [k for k in row_credits if k.startswith(f'{ci}:')]
                if len(card_rows) == 4 and not any(powr.get('card') == ci for powr in powers):
                    available = [x for x in POWER_POOL if x not in [q['name'] for q in powers]]
                    if available and s['powers_enabled']:
                        power = random.choice(available)
                        powers.append({'name': power, 'card': ci, 'used': False, 'earned_at': time.time()})
                        add_feed(p['session_id'],'power',f'🎁 POWER WHEEL: {p["alias"]} earned {power} on Card {chr(65+ci)}')
        allnums = set(n for row in card for n in row.values())
        if ci not in blackouts and allnums.issubset(marks):
            blackouts.add(ci); points += 50; changed = True
            add_feed(p['session_id'],'blackout',f'🔥 BLACKOUT! {p["alias"]} completed Card {chr(65+ci)} (+50)')
    db().execute('UPDATE players SET points=?, row_credits=?, blackouts=?, powers=? WHERE id=?',
                 (points,json.dumps(list(row_credits)),json.dumps(list(blackouts)),json.dumps(powers),p['id']))
    db().commit()

def player_dict(p):
    return dict(p) | {'cards': jload(p['cards'], []), 'marks': jload(p['marks'], []), 'row_credits': jload(p['row_credits'], []), 'blackouts': jload(p['blackouts'], []), 'powers': jload(p['powers'], [])}

def leaderboard(session_id):
    rows = db().execute('SELECT * FROM players WHERE session_id=?',(session_id,)).fetchall()
    data=[]
    for p in rows:
        d=player_dict(p); remaining=75-len(set(d['marks']))
        data.append({'id':p['id'],'alias':p['alias'],'points':p['points'],'blackouts':len(d['blackouts']),'rows':len(d['row_credits']),'remaining':remaining,'powers':sum(1 for x in d['powers'] if not x.get('used')),'progress': f"{len(d['row_credits'])%4}/4",'status':p['status']})
    return sorted(data, key=lambda x: (-x['blackouts'], -x['points'], -x['rows'], x['remaining']))

@app.route('/')
def index(): return redirect('/player')
@app.route('/player')
def player(): return render_template('player.html')
@app.route('/host')
def host(): return render_template('host.html')
@app.route('/tv')
def tv(): return render_template('tv.html')

@app.route('/api/state')
def state():
    s=active_session(); pid=flask_session.get('player_id')
    p = db().execute('SELECT * FROM players WHERE id=?',(pid,)).fetchone() if pid else None
    feed=[dict(x) for x in db().execute('SELECT * FROM feed WHERE session_id=? ORDER BY id DESC LIMIT 20',(s['id'],)).fetchall()]
    return jsonify({'session':dict(s),'called_numbers':jload(s['called_numbers'],[]),'remaining_numbers':jload(s['remaining_numbers'],[]),'player':player_dict(p) if p else None,'leaderboard':leaderboard(s['id']),'feed':feed})

@app.route('/api/rsvp', methods=['POST'])
def rsvp():
    s=active_session()
    if s['status'] != 'lobby': return jsonify({'error':'No late joins allowed after the game starts.'}),400
    phone=request.json.get('phone','').strip(); alias=clean_alias(request.json.get('alias',''))
    if not phone: return jsonify({'error':'Phone number required for reserved seat recovery.'}),400
    cards=make_cards(); marks=[]; row_credits=[]; blackouts=[]
    try:
        cur=db().execute('INSERT INTO players(session_id,phone,alias,cards,marks,row_credits,blackouts) VALUES(?,?,?,?,?,?,?)',
            (s['id'], phone, alias, json.dumps(cards), json.dumps(marks), json.dumps(row_credits), json.dumps(blackouts)))
        db().commit(); flask_session['player_id']=cur.lastrowid
        add_feed(s['id'],'join',f'✅ {alias} RSVP confirmed')
    except sqlite3.IntegrityError:
        p=db().execute('SELECT * FROM players WHERE session_id=? AND phone=?',(s['id'],phone)).fetchone()
        if p:
            flask_session['player_id']=p['id']; return jsonify({'ok':True,'recovered':True})
        return jsonify({'error':'Alias already taken. Choose another alias.'}),400
    return jsonify({'ok':True})

@app.route('/api/host/update', methods=['POST'])
def host_update():
    s=active_session()
    if s['locked']: return jsonify({'error':'Rules are locked after start.'}),400
    data=request.json
    db().execute('UPDATE sessions SET venue=?, blackout_goal=?, triple_winners_goal=?, countdown=?, mark_mode=?, tv_enabled=?, powers_enabled=? WHERE id=?',
        (data.get('venue',s['venue']), int(data.get('blackout_goal',s['blackout_goal'])), int(data.get('triple_winners_goal',s['triple_winners_goal'])), int(data.get('countdown',s['countdown'])), data.get('mark_mode',s['mark_mode']), int(bool(data.get('tv_enabled',s['tv_enabled']))), int(bool(data.get('powers_enabled',s['powers_enabled']))), s['id']))
    db().commit(); return jsonify({'ok':True})

@app.route('/api/host/start', methods=['POST'])
def start():
    s=active_session();
    db().execute("UPDATE sessions SET status='running', locked=1, started_at=?, remaining_numbers=? WHERE id=?",(datetime.utcnow().isoformat(),json.dumps(CALL_POOL.copy()),s['id']))
    db().commit(); add_feed(s['id'],'start','▶ Battle Bingo started. Lobby locked. No late joins.')
    return jsonify({'ok':True})

@app.route('/api/host/call', methods=['POST'])
def call_next():
    s=active_session(); remaining=jload(s['remaining_numbers'], CALL_POOL.copy()); called=jload(s['called_numbers'], [])
    if not remaining: return jsonify({'error':'No numbers remaining'}),400
    n=random.choice(remaining); remaining.remove(n); called.append(n)
    db().execute('UPDATE sessions SET current_number=?, called_numbers=?, remaining_numbers=? WHERE id=?',(n,json.dumps(called),json.dumps(remaining),s['id']))
    db().commit(); add_feed(s['id'],'call',f'📣 Number called: {n}')
    if s['mark_mode']=='auto':
        for p in db().execute('SELECT * FROM players WHERE session_id=?',(s['id'],)).fetchall():
            marks=set(jload(p['marks'], []));
            cards=jload(p['cards'], [])
            if any(n in row.values() for card in cards for row in card):
                marks.add(n); db().execute('UPDATE players SET marks=?, points=points+5 WHERE id=?',(json.dumps(list(marks)),p['id'])); db().commit(); evaluate_player(db().execute('SELECT * FROM players WHERE id=?',(p['id'],)).fetchone(), s)
    return jsonify({'ok':True,'number':n})

@app.route('/api/mark', methods=['POST'])
def mark():
    s=active_session(); p=db().execute('SELECT * FROM players WHERE id=?',(flask_session.get('player_id'),)).fetchone()
    if not p: return jsonify({'error':'Not RSVP’d'}),400
    n=int(request.json.get('number'))
    if n != s['current_number']: return jsonify({'error':'Only the current called number can be marked.'}),400
    marks=set(jload(p['marks'], []));
    if n not in marks:
        marks.add(n); db().execute('UPDATE players SET marks=?, points=points+5 WHERE id=?',(json.dumps(list(marks)),p['id'])); db().commit(); evaluate_player(db().execute('SELECT * FROM players WHERE id=?',(p['id'],)).fetchone(), s)
    return jsonify({'ok':True})

@app.route('/api/use_power', methods=['POST'])
def use_power():
    s=active_session(); p=db().execute('SELECT * FROM players WHERE id=?',(flask_session.get('player_id'),)).fetchone()
    if not p: return jsonify({'error':'Not RSVP’d'}),400
    current_call=s['current_number'] or 0
    if p['power_cooldown_call']==current_call: return jsonify({'error':'Only 1 power may be used per countdown cycle.'}),400
    powers=jload(p['powers'], []); idx=int(request.json.get('index',0))
    if idx>=len(powers) or powers[idx].get('used'): return jsonify({'error':'Power unavailable.'}),400
    name=powers[idx]['name']; powers[idx]['used']=True
    marks=set(jload(p['marks'], []));
    if name=='Lucky Spot':
        # mark first unmarked number on this player's cards for prototype
        nums=[n for card in jload(p['cards'],[]) for row in card for n in row.values() if n not in marks]
        if nums: marks.add(random.choice(nums)); db().execute('UPDATE players SET marks=? WHERE id=?',(json.dumps(list(marks)),p['id']))
    elif name=='Power Swap':
        lb=[x for x in leaderboard(s['id']) if x['id']!=p['id'] and x['powers']>0]
        if lb:
            target=random.choice(lb); add_feed(s['id'],'power',f'🔄 {p["alias"]} used Power Swap with {target["alias"]}')
    db().execute('UPDATE players SET powers=?, power_cooldown_call=?, points=points+10 WHERE id=?',(json.dumps(powers),current_call,p['id']))
    db().commit(); add_feed(s['id'],'power',f'⚡ {p["alias"]} used {name} (+10)')
    evaluate_player(db().execute('SELECT * FROM players WHERE id=?',(p['id'],)).fetchone(), s)
    return jsonify({'ok':True})

@app.route('/api/host/alias', methods=['POST'])
def alias_edit():
    pid=int(request.json['player_id']); alias=clean_alias(request.json.get('alias') or random_alias())
    db().execute('UPDATE players SET alias=? WHERE id=?',(alias,pid)); db().commit(); return jsonify({'ok':True,'alias':alias})

@app.route('/api/host/reset', methods=['POST'])
def reset():
    mode=request.json.get('mode','session')
    if mode=='everything':
        db().execute('DELETE FROM players'); db().execute('DELETE FROM feed'); db().execute('DELETE FROM prizes'); db().execute('DELETE FROM sessions'); db().commit(); active_session()
    else:
        s=active_session(); db().execute("UPDATE sessions SET status='lobby', locked=0, called_numbers='[]', remaining_numbers=?, current_number=NULL, started_at=NULL, ended_at=NULL WHERE id=?",(json.dumps(CALL_POOL.copy()),s['id']))
        db().execute('DELETE FROM players WHERE session_id=?',(s['id'],)); db().execute('DELETE FROM feed WHERE session_id=?',(s['id'],)); db().commit()
    return jsonify({'ok':True})

# Initialize database when imported by Gunicorn/Render.
init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT',5000)))
