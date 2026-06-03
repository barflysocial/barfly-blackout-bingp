import os, json, random, string, re, functools, threading, time, csv
from io import BytesIO, StringIO
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort, session, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
import qrcode
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-render')
uri = os.environ.get('DATABASE_URL', 'sqlite:///battle_bingo.db')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

POWERS = ['Freeze','Fire','Recover']
WIN_CALL_LETTERS = ('W','I','N')
WIN_CALLS_PER_LETTER = 75
POWER_EVERY_ROWS = 3
POWER_HOLD_LIMIT = 3
LEGACY_POWER_NAMES = {'Second Chance':'Fire'}
BAD_WORDS = {'fuck','shit','bitch','asshole','dick','pussy','cunt','nigger','faggot','slut','whore'}
GAMEPLAY_FEED_KINDS = {'line','power','full_clear','afk','badge','game_over','ranking'}

class Game(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    code=db.Column(db.String(12), unique=True, index=True)
    title=db.Column(db.String(140), default='Battle Bingo')
    venue=db.Column(db.String(140), default='Barfly Social')
    starts_at=db.Column(db.String(80), default='')
    scheduled_start_at=db.Column(db.DateTime, nullable=True)
    rsvp_open_at=db.Column(db.DateTime, nullable=True)
    rsvp_close_at=db.Column(db.DateTime, nullable=True)
    schedule_timezone=db.Column(db.String(80), default='America/Chicago')
    lobby_paused=db.Column(db.Boolean, default=False)
    title_image=db.Column(db.Text, default='')
    sponsor_text=db.Column(db.String(200), default='')
    venue_logo=db.Column(db.Text, default='')
    status=db.Column(db.String(20), default='rsvp')
    countdown=db.Column(db.Integer, default=10)
    mark_mode=db.Column(db.String(12), default='manual')
    call_mode=db.Column(db.String(12), default='manual')
    blackouts_to_win=db.Column(db.Integer, default=3)
    triple_winners_needed=db.Column(db.Integer, default=1)
    tv_enabled=db.Column(db.Boolean, default=True)
    powers_enabled=db.Column(db.Boolean, default=True)
    board_mode=db.Column(db.String(20), default='numbers')
    rules_locked=db.Column(db.Boolean, default=False)
    called_json=db.Column(db.Text, default='[]')
    call_pool_json=db.Column(db.Text, default='[]')
    current_number=db.Column(db.Integer, nullable=True)
    current_call_index=db.Column(db.Integer, default=0)
    last_call_at=db.Column(db.DateTime, nullable=True)
    power_wheel_json=db.Column(db.Text, default='{}')
    finalized=db.Column(db.Boolean, default=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class Player(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    game_id=db.Column(db.Integer, db.ForeignKey('game.id'), index=True)
    name=db.Column(db.String(90), default='')
    phone=db.Column(db.String(20), index=True)
    alias=db.Column(db.String(40), default='Player')
    instagram=db.Column(db.String(80), default='')
    cards_json=db.Column(db.Text, default='[]')
    marked_json=db.Column(db.Text, default='[]')
    clovers_json=db.Column(db.Text, default='[]')
    row_credit_json=db.Column(db.Text, default='{}')
    power_cards_json=db.Column(db.Text, default='[]')
    powers_json=db.Column(db.Text, default='[]')
    used_powers_json=db.Column(db.Text, default='[]')
    points=db.Column(db.Integer, default=0)
    blackouts=db.Column(db.Integer, default=0)
    blackout_times_json=db.Column(db.Text, default='[]')
    last_power_call_index=db.Column(db.Integer, default=-1)
    frozen_number=db.Column(db.Integer, nullable=True)
    frozen_until_at=db.Column(db.DateTime, nullable=True)
    shield=db.Column(db.Boolean, default=False)
    mirror=db.Column(db.Boolean, default=False)
    blocked_rows_json=db.Column(db.Text, default='[]')
    afk_misses=db.Column(db.Integer, default=0)
    status=db.Column(db.String(20), default='active')
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    game=db.relationship('Game', backref='players')

class Feed(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    game_id=db.Column(db.Integer, db.ForeignKey('game.id'), index=True)
    text=db.Column(db.Text)
    kind=db.Column(db.String(40), default='info')
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class Prize(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    game_id=db.Column(db.Integer, db.ForeignKey('game.id'), index=True)
    label=db.Column(db.String(80))
    sponsor=db.Column(db.String(120))
    prize=db.Column(db.String(180))
    notes=db.Column(db.Text, default='')

class Stat(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    phone=db.Column(db.String(20), index=True)
    alias=db.Column(db.String(40))
    games=db.Column(db.Integer, default=0)
    wins=db.Column(db.Integer, default=0)
    blackouts=db.Column(db.Integer, default=0)
    points=db.Column(db.Integer, default=0)
    powers_earned=db.Column(db.Integer, default=0)
    powers_used=db.Column(db.Integer, default=0)

class Achievement(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    game_id=db.Column(db.Integer, index=True)
    player_id=db.Column(db.Integer, index=True)
    alias=db.Column(db.String(40))
    badge=db.Column(db.String(80))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

_schema_checked = False

def ensure_schema():
    global _schema_checked
    db.create_all()
    if _schema_checked:
        return
    try:
        cols={c['name'] for c in inspect(db.engine).get_columns('game')}
        additions={
            'scheduled_start_at':'TIMESTAMP',
            'rsvp_open_at':'TIMESTAMP',
            'rsvp_close_at':'TIMESTAMP',
            'schedule_timezone':"VARCHAR(80) DEFAULT 'America/Chicago'",
            'lobby_paused':'BOOLEAN DEFAULT FALSE',
        }
        for name, typ in additions.items():
            if name not in cols:
                db.session.execute(text(f'ALTER TABLE game ADD COLUMN {name} {typ}'))
        pcols={c['name'] for c in inspect(db.engine).get_columns('player')}
        if 'instagram' not in pcols:
            db.session.execute(text("ALTER TABLE player ADD COLUMN instagram VARCHAR(80) DEFAULT ''"))
        if 'frozen_until_at' not in pcols:
            db.session.execute(text("ALTER TABLE player ADD COLUMN frozen_until_at TIMESTAMP"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    _schema_checked=True

@app.before_request
def ensure_db():
    ensure_schema()

def clean_phone(p): return re.sub(r'\D','',p or '')[-10:]
def j(raw, default):
    try: return json.loads(raw or '')
    except Exception: return default
def dump(x): return json.dumps(x, separators=(',',':'))
def normalize_power_name(name): return LEGACY_POWER_NAMES.get(name, name)
def sanitize_power_inventory(p):
    held=j(p.powers_json,[])
    cleaned=[]
    changed=False
    for item in held:
        if not isinstance(item, dict):
            changed=True
            continue
        nm=normalize_power_name(item.get('name'))
        if nm not in POWERS:
            changed=True
            continue
        if nm != item.get('name'):
            item=dict(item); item['name']=nm; changed=True
        cleaned.append(item)
    if changed:
        p.powers_json=dump(cleaned)
    return cleaned
def now_iso(): return datetime.utcnow().isoformat(timespec='milliseconds')+'Z'
def game_code():
    while True:
        c=''.join(random.choices(string.ascii_uppercase+string.digits,k=6))
        if not Game.query.filter_by(code=c).first(): return c
def feed(game_id, text, kind='info', commit=False):
    db.session.add(Feed(game_id=game_id, text=text, kind=kind))
    if commit: db.session.commit()
def bad_alias(a):
    low=re.sub(r'[^a-z0-9]','',(a or '').lower())
    return any(w in low for w in BAD_WORDS)
def gen_alias():
    return random.choice(['Blue','Lucky','Silver','Green','Golden','Neon','Bayou','Royal','Velvet','Cajun']) + random.choice(['Tiger','Falcon','Otter','Dragon','Wolf','Clover','Ace','Wizard','Gator','Hawk']) + str(random.randint(10,99))
def win_call_parts(n):
    try:
        n=int(n)
    except Exception:
        return None, None
    if 1 <= n <= WIN_CALLS_PER_LETTER:
        return 'W', n
    if WIN_CALLS_PER_LETTER < n <= WIN_CALLS_PER_LETTER * 2:
        return 'I', n - WIN_CALLS_PER_LETTER
    if WIN_CALLS_PER_LETTER * 2 < n <= WIN_CALLS_PER_LETTER * 3:
        return 'N', n - (WIN_CALLS_PER_LETTER * 2)
    return None, n

def call_label(n, mode='numbers'):
    if not n: return '—'
    if mode == 'win':
        letter, num = win_call_parts(n)
        return f'{letter}{num}' if letter else str(n)
    return str(n)

def cell_label(n, mode='numbers'):
    if not n: return '—'
    if mode == 'win':
        letter, num = win_call_parts(n)
        return str(num) if letter else str(n)
    return str(n)

def call_pool_for_mode(mode='numbers'):
    return list(range(1, WIN_CALLS_PER_LETTER * 3 + 1)) if mode == 'win' else list(range(1,76))

def shuffled_call_pool(mode='numbers'):
    pool=call_pool_for_mode(mode)
    random.shuffle(pool)
    return pool

app.jinja_env.globals['call_label']=call_label
app.jinja_env.globals['cell_label']=cell_label

def parse_local_datetime(value, tz_name='America/Chicago'):
    value=(value or '').strip()
    if not value:
        return None
    try:
        dt=datetime.fromisoformat(value)
        if dt.tzinfo is None:
            if ZoneInfo:
                dt=dt.replace(tzinfo=ZoneInfo(tz_name or 'America/Chicago'))
            else:
                dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None

def format_local_datetime(dt, tz_name='America/Chicago'):
    if not dt:
        return ''
    try:
        aware=dt.replace(tzinfo=timezone.utc)
        if ZoneInfo:
            aware=aware.astimezone(ZoneInfo(tz_name or 'America/Chicago'))
        return aware.strftime('%Y-%m-%d %I:%M %p')
    except Exception:
        return str(dt)

app.jinja_env.globals['format_local_datetime']=format_local_datetime

def format_seconds(total):
    try: total=max(0,int(total))
    except Exception: total=0
    h=total//3600; m=(total%3600)//60; sec=total%60
    return f'{h}:{m:02d}:{sec:02d}' if h else f'{m}:{sec:02d}'
app.jinja_env.globals['format_seconds']=format_seconds

def dt_iso(dt):
    if not dt:
        return None
    try:
        return dt.replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    except Exception:
        return None

def game_timer_payload(g):
    now=datetime.utcnow()
    call_ends_at=None
    lobby_ends_at=None
    if g.status=='started' and g.last_call_at:
        wheel=j(g.power_wheel_json,{})
        if not wheel.get('active'):
            call_ends_at=g.last_call_at+timedelta(seconds=max(1, int(g.countdown or 10)))
    if g.status!='started' and getattr(g, 'scheduled_start_at', None):
        lobby_ends_at=g.scheduled_start_at
    return {
        'server_now': dt_iso(now),
        'call_started_at': dt_iso(g.last_call_at),
        'call_ends_at': dt_iso(call_ends_at),
        'lobby_ends_at': dt_iso(lobby_ends_at),
        'countdown_duration': int(g.countdown or 10),
    }

def game_leaderboard_payload(g):
    lb=[]
    for p in leaderboard(g.id):
        lb.append({'id':p.id,'alias':p.alias,'points':as_int(p.points),'lines_left':lines_left(j(p.cards_json,[]),p),'powers':len(j(p.powers_json,[])),'progress':len(j(p.row_credit_json,{}))%POWER_EVERY_ROWS,'rows':len(j(p.row_credit_json,{})),'afk':False})
    return lb

def game_winners_payload(g):
    return [{'id':p.id,'alias':p.alias,'place':i+1,'points':as_int(p.points),'timestamp':(j(p.blackout_times_json,[]) or [''])[0]} for i,p in enumerate(full_clear_winners(g.id)[:10])]

def game_feed_payload(g, limit=30):
    feeds=Feed.query.filter_by(game_id=g.id).order_by(Feed.id.desc()).limit(limit).all()
    return [{'text':f.text,'kind':f.kind} for f in feeds if f.kind in GAMEPLAY_FEED_KINDS]


@app.route('/healthz')
def healthz():
    return {'ok': True, 'service': 'battle-bingo'}

def host_pin_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        pin=os.environ.get('HOST_PIN','').strip()
        if not pin:
            return fn(*args, **kwargs)
        supplied=request.headers.get('X-Host-Pin') or request.args.get('pin') or request.form.get('pin') or session.get('host_pin')
        if supplied==pin:
            session['host_pin']=pin
            return fn(*args, **kwargs)
        if request.method=='POST':
            return render_template('message.html', title='Host Locked', body='Host PIN required.'), 403
        return render_template('host_login.html')
    return wrapper

def generate_cards(mode='numbers'):
    # Battle Bingo WIN mode uses three exact call columns.
    # W, I, and N each have their own 1-75 number pool, encoded internally
    # as W=1-75, I=76-150, and N=151-225. The player card shows only
    # the number inside the W/I/N column, while calls display as W42/I42/N42.
    if mode == 'win':
        w=random.sample(range(1,76),25)
        i=random.sample(range(76,151),25)
        n=random.sample(range(151,226),25)
        return [[w[x], i[x], n[x]] for x in range(25)]
    nums=list(range(1,76)); random.shuffle(nums)
    return [nums[i*3:(i+1)*3] for i in range(25)]

def all_card_nums(board): return [n for row in board for n in row]
def rows_completed(board, marked):
    ms=set(marked); done=[]
    for ri,row in enumerate(board):
        if all(n in ms for n in row): done.append(str(ri))
    return done
def lines_left(board, p):
    return max(0, len(board)-len(j(p.row_credit_json,{})))
def full_clear_count(board, marked):
    ms=set(marked)
    return 1 if board and all(n in ms for row in board for n in row) else 0
def valid_unblocked_row(p, ri):
    return str(ri) not in j(p.blocked_rows_json, [])

def award_achievement(p, badge):
    exists=Achievement.query.filter_by(game_id=p.game_id, player_id=p.id, badge=badge).first()
    if not exists:
        db.session.add(Achievement(game_id=p.game_id, player_id=p.id, alias=p.alias, badge=badge))
        feed(p.game_id, f'🏅 {p.alias} earned badge: {badge}', 'badge')

def recalc_player(p, newly_marked=None):
    board=j(p.cards_json,[])
    marked=j(p.marked_json,[])
    credited=set(j(p.row_credit_json,{}).keys())
    if newly_marked:
        p.points = as_int(p.points) + 5
    new_rows=[r for r in rows_completed(board, marked) if r not in credited]
    for r in new_rows:
        ri=int(r)
        if not valid_unblocked_row(p,ri):
            continue
        credited.add(r); p.points += 25
        feed(p.game_id, f'🔥 {p.alias} cleared a line. Lines left: {len(board)-len(credited)}', 'line')
    p.row_credit_json=dump({r:True for r in credited})
    maybe_award_line_powers(p)
    old_b=p.blackouts; new_b=full_clear_count(board, marked)
    if new_b>old_b:
        times=j(p.blackout_times_json,[])
        p.points = as_int(p.points) + 50; times.append(now_iso())
        p.blackouts=new_b; p.blackout_times_json=dump(times)
        db.session.flush()
        place=player_clearout_place(p) or len(full_clear_winners(p.game_id))
        suffix = 'st' if place == 1 else 'nd' if place == 2 else 'rd' if place == 3 else 'th'
        feed(p.game_id, f'🏆 CLEAR OUT! {place}{suffix} Place: {p.alias}', 'full_clear')
        award_achievement(p,'Full Clear')

def power_thresholds_processed(p):
    processed=[]
    for item in j(p.power_cards_json,[]):
        try:
            processed.append(int(item))
        except Exception:
            continue
    return sorted(set(processed))


def next_cycle_power(processed_count):
    return POWERS[processed_count % len(POWERS)]


def maybe_award_line_powers(p):
    g=Game.query.get(p.game_id)
    if not g or not g.powers_enabled:
        return
    cleared=len(j(p.row_credit_json,{}))
    processed=power_thresholds_processed(p)
    processed_set=set(processed)
    # Earn 1 power every 3 cleared rows. Inventory is capped at 3 powers.
    # If a player's inventory is full at an earning threshold, that threshold is
    # consumed/skipped instead of being banked for later.
    for threshold in range(POWER_EVERY_ROWS, cleared+1, POWER_EVERY_ROWS):
        if threshold in processed_set:
            continue
        cycle_index=len(processed)
        held=sanitize_power_inventory(p)
        if len(held)>=POWER_HOLD_LIMIT:
            processed.append(threshold)
            processed_set.add(threshold)
            p.power_cards_json=dump(processed)
            feed(p.game_id, f'⚠️ {p.alias} earned a power at {threshold} cleared lines, but all 3 power slots were full.', 'power')
            return
        if award_power(p, threshold, cycle_index=cycle_index):
            processed.append(threshold)
            processed_set.add(threshold)
            p.power_cards_json=dump(processed)
        return


def award_power(p, threshold=None, cycle_index=None):
    g=Game.query.get(p.game_id)
    if not g or not g.powers_enabled: return False
    held=sanitize_power_inventory(p)
    if len(held)>=POWER_HOLD_LIMIT: return False
    if cycle_index is None:
        cycle_index=len(power_thresholds_processed(p))
    name=next_cycle_power(cycle_index)
    held.append({'name':name,'earned_at':now_iso(),'used':False,'threshold':threshold})
    p.powers_json=dump(held)
    g.power_wheel_json=dump({'active':True,'alias':p.alias,'power':name,'until':(datetime.utcnow()+timedelta(seconds=5)).isoformat()+'Z'})
    feed(p.game_id, f'🎁 {p.alias} earned {name} for clearing {threshold} lines', 'power')
    if len(power_thresholds_processed(p))==0: award_achievement(p,'First Blood')
    return True


def has_power(p, name):
    return any(normalize_power_name(x.get('name')) == name for x in sanitize_power_inventory(p))

def consume_power(p, name, score=True):
    held=sanitize_power_inventory(p)
    for item in list(held):
        if normalize_power_name(item.get('name')) == name:
            held.remove(item)
            used=j(p.used_powers_json,[])
            item=dict(item)
            item['used_at']=now_iso()
            item['auto_used']=name in ('Fire','Recover')
            used.append(item)
            p.powers_json=dump(held)
            p.used_powers_json=dump(used)
            if score:
                p.points=as_int(p.points)+10
            return item
    return None

def auto_recover_missed_call(g, p, n):
    board_nums=set(all_card_nums(j(p.cards_json,[])))
    marked=set(j(p.marked_json,[]))
    if n not in board_nums or n in marked:
        return False
    if not has_power(p, 'Recover'):
        return False
    # The missed call is over now, so Recover is allowed to repair even a
    # freeze-caused miss. It cannot mark random or future calls.
    if p.frozen_number == n:
        p.frozen_number=None
        p.frozen_until_at=None
    consumed=consume_power(p, 'Recover')
    if not consumed:
        return False
    ok=mark_number(p, n, is_auto=True, ignore_freeze=True)
    if ok:
        feed(g.id, f'✚ {p.alias} auto-used Recover to mark missed {call_label(n, g.board_mode)}', 'power')
        return True
    return False

def process_previous_call_misses(g, prev):
    if not prev or g.mark_mode != 'manual':
        return
    for p in Player.query.filter_by(game_id=g.id, status='active').all():
        board=j(p.cards_json,[])
        marked=j(p.marked_json,[])
        if prev in all_card_nums(board) and prev not in marked:
            recovered=auto_recover_missed_call(g, p, prev)
            if not recovered and p.frozen_number != prev:
                p.afk_misses += 1
    for p in Player.query.filter_by(game_id=g.id, status='active').all():
        if p.frozen_number == prev:
            p.frozen_number=None
            p.frozen_until_at=None
    check_end(g)


def full_clear_winners(game_id):
    winners=[]
    for p in Player.query.filter(Player.game_id==game_id, Player.status=='active', Player.blackouts>=1).all():
        times=j(p.blackout_times_json,[])
        winners.append((times[0] if times else '9999-99-99T99:99:99.999Z', p))
    return [p for _,p in sorted(winners, key=lambda x:x[0])]

def player_clearout_place(p):
    if not p or p.blackouts < 1:
        return None
    winners=full_clear_winners(p.game_id)
    for i,w in enumerate(winners, start=1):
        if w.id == p.id:
            return i
    return None

def leaderboard(game_id):
    players=Player.query.filter_by(game_id=game_id, status='active').all()
    def key(p):
        board=j(p.cards_json,[])
        left=lines_left(board,p)
        times=j(p.blackout_times_json,[])
        latest=times[-1] if times else '9999-99-99T99:99:99.999Z'
        return (left, latest, -as_int(p.points))
    return sorted(players, key=key)

def lobby_seconds_remaining(g):
    if not getattr(g, 'scheduled_start_at', None):
        return None
    if g.status in ('started','ended','cancelled'):
        return 0
    return max(0, int((g.scheduled_start_at - datetime.utcnow()).total_seconds()))

def start_game_now(g, reason='Game started'):
    if g.status in ('started','ended','cancelled'):
        return
    g.status='started'
    g.rules_locked=True
    g.lobby_paused=False
    if not j(g.call_pool_json,[]):
        g.call_pool_json=dump(shuffled_call_pool(g.board_mode))
    feed(g.id, f'▶️ {reason}. Rules are locked.', 'admin')
    if not g.current_number:
        call_next(g)

def maybe_update_schedule(g):
    if g.status in ('ended','cancelled','started'):
        return
    if getattr(g, 'lobby_paused', False):
        return
    now=datetime.utcnow()
    if g.rsvp_open_at and g.status=='draft' and now>=g.rsvp_open_at:
        g.status='lobby'
        feed(g.id, '✅ RSVP is open. Lobby countdown started.', 'admin')
    if g.scheduled_start_at and g.status in ('rsvp','lobby','draft') and now>=g.scheduled_start_at:
        start_game_now(g, 'Scheduled start time reached')

def game_seconds_remaining(g):
    if g.status=='ended': return 0
    if g.status!='started' or not g.last_call_at: return g.countdown
    wheel=j(g.power_wheel_json,{})
    if wheel.get('active'):
        until=datetime.fromisoformat(wheel['until'].replace('Z',''))
        if datetime.utcnow()<until: return g.countdown
        wheel['active']=False; g.power_wheel_json=dump(wheel)
    elapsed=(datetime.utcnow()-g.last_call_at).total_seconds()
    return max(0, int(g.countdown - elapsed))

def maybe_auto_call(g):
    maybe_update_schedule(g)
    if g.status!='started': return
    wheel=j(g.power_wheel_json,{})
    if wheel.get('active'):
        until=datetime.fromisoformat(wheel['until'].replace('Z',''))
        if datetime.utcnow()<until: return
        wheel['active']=False; g.power_wheel_json=dump(wheel)
        g.last_call_at=datetime.utcnow()
    if g.call_mode=='auto' and (not g.last_call_at or (datetime.utcnow()-g.last_call_at).total_seconds() >= g.countdown):
        call_next(g)
        db.session.commit()

def freeze_active(p, n=None):
    if not p.frozen_number:
        return False
    if n is not None and p.frozen_number != n:
        return False
    until=getattr(p, 'frozen_until_at', None)
    if not until:
        return False
    if datetime.utcnow() >= until:
        p.frozen_number=None
        p.frozen_until_at=None
        return False
    return True

def freeze_remaining_seconds(p):
    until=getattr(p, 'frozen_until_at', None)
    if not p.frozen_number or not until:
        return 0
    remaining=int((until-datetime.utcnow()).total_seconds())
    if remaining <= 0:
        p.frozen_number=None
        p.frozen_until_at=None
        return 0
    return remaining

def mark_number(p, n, is_auto=False, ignore_freeze=False):
    g=Game.query.get(p.game_id)
    if not ignore_freeze and freeze_active(p, n):
        return False
    board=j(p.cards_json,[]); nums=set(all_card_nums(board))
    if n not in nums: return False
    marked=j(p.marked_json,[])
    if n in marked: return False
    marked.append(n); p.marked_json=dump(marked); p.afk_misses=0
    recalc_player(p, newly_marked=n)
    return True

def call_next(g):
    if g.status!='started': return
    # End the previous call first. Automatic Recover repairs one missed
    # previously called number after the call window closes.
    prev=g.current_number
    process_previous_call_misses(g, prev)
    if g.status == 'ended':
        return
    # clear expired freeze windows and row blocks each cycle
    for p in Player.query.filter_by(game_id=g.id).all():
        freeze_remaining_seconds(p)
        p.blocked_rows_json='[]'
    called=j(g.called_json,[])
    pool=j(g.call_pool_json,[])
    if not pool:
        pool=shuffled_call_pool(g.board_mode)
    remaining=[n for n in pool if n not in called]
    if not remaining:
        g.status='ended'
        g.current_number=None
        feed(g.id, '🏁 GAME OVER: all numbers have been called', 'game_over')
        finalize_stats(g)
        return
    n=remaining[0]
    called.append(n); g.current_number=n; g.current_call_index=(g.current_call_index or 0)+1
    g.called_json=dump(called); g.call_pool_json=dump(pool); g.last_call_at=datetime.utcnow()
    for pp in Player.query.filter_by(game_id=g.id, status='active').all():
        if pp.frozen_number == -1:
            pp.frozen_number = n
            pp.frozen_until_at = datetime.utcnow()+timedelta(seconds=max(1, int(g.countdown or 10)))
    # Do not write number calls to Battle Feed. Feed is player activity only.
    if g.mark_mode=='auto':
        for p in Player.query.filter_by(game_id=g.id, status='active').all():
            mark_number(p,n,is_auto=True)
    check_end(g)

def check_end(g):
    winners=Player.query.filter(Player.game_id==g.id, Player.status=='active', Player.blackouts>=1).count()
    if winners>=g.triple_winners_needed:
        g.status='ended'; feed(g.id, f'🏁 Game over: {winners} Full Clear winner(s)', 'game_over')
        finalize_stats(g)

def as_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default

def finalize_stats(g):
    # Finalizing stats must never depend on SQLAlchemy column defaults already
    # being present on a new Python object. New Stat rows can have None values
    # until inserted, and older database rows may also contain NULL values.
    if g.finalized:
        return
    lb=leaderboard(g.id)
    for idx,p in enumerate(lb):
        phone=(p.phone or '').strip()
        s=Stat.query.filter_by(phone=phone).first() if phone else None
        if not s:
            s=Stat(
                phone=phone,
                alias=p.alias,
                games=0,
                wins=0,
                blackouts=0,
                points=0,
                powers_earned=0,
                powers_used=0
            )
            db.session.add(s)
        s.alias=p.alias
        s.games=as_int(s.games)+1
        s.blackouts=as_int(s.blackouts)+as_int(p.blackouts)
        s.points=as_int(s.points)+as_int(p.points)
        s.powers_earned=as_int(s.powers_earned)+len(j(p.powers_json,[]))+len(j(p.used_powers_json,[]))
        s.powers_used=as_int(s.powers_used)+len(j(p.used_powers_json,[]))
        if idx==0:
            s.wins=as_int(s.wins)+1
            award_achievement(p,'Battle Bingo Champion')
    g.finalized=True

def reset_game(g, clear_players=False, clear_all=False):
    g.status='rsvp'; g.rules_locked=False; g.called_json='[]'; g.call_pool_json='[]'; g.current_number=None; g.current_call_index=0; g.last_call_at=None; g.power_wheel_json='{}'; g.finalized=False
    if clear_all:
        Prize.query.filter_by(game_id=g.id).delete()
    if clear_players:
        Player.query.filter_by(game_id=g.id).delete()
    else:
        for p in Player.query.filter_by(game_id=g.id).all():
            p.cards_json=dump(generate_cards(g.board_mode)); p.marked_json='[]'; p.clovers_json='[]'; p.row_credit_json='{}'; p.power_cards_json='[]'; p.powers_json='[]'; p.used_powers_json='[]'; p.points=0; p.blackouts=0; p.blackout_times_json='[]'; p.last_power_call_index=-1; p.frozen_number=None; p.frozen_until_at=None; p.shield=False; p.mirror=False; p.blocked_rows_json='[]'; p.afk_misses=0; p.status='active'
    Feed.query.filter_by(game_id=g.id).delete()
    feed(g.id,'🗑️ Session reset','admin')


def clone_game(source):
    """Create a new independent session using the same venue/game settings.
    Players, calls, feeds, prizes, rankings, and powers are NOT copied.
    """
    new_code = game_code()
    clone = Game(
        code=new_code,
        title=(source.title or 'Battle Bingo') + ' Copy',
        venue=source.venue,
        starts_at=source.starts_at,
        scheduled_start_at=source.scheduled_start_at,
        rsvp_open_at=None,
        rsvp_close_at=None,
        schedule_timezone=source.schedule_timezone,
        lobby_paused=False,
        title_image=source.title_image,
        sponsor_text=source.sponsor_text,
        venue_logo=source.venue_logo,
        status='lobby' if source.scheduled_start_at else 'rsvp',
        countdown=source.countdown,
        mark_mode=source.mark_mode,
        call_mode=source.call_mode,
        blackouts_to_win=source.blackouts_to_win,
        triple_winners_needed=source.triple_winners_needed,
        tv_enabled=source.tv_enabled,
        powers_enabled=source.powers_enabled,
        board_mode=source.board_mode,
        rules_locked=False,
        called_json='[]',
        call_pool_json='[]',
        current_number=None,
        current_call_index=0,
        last_call_at=None,
        power_wheel_json='{}',
        finalized=False,
    )
    db.session.add(clone)
    db.session.flush()
    # Copy first-place prize templates only, not winners.
    for pr in Prize.query.filter_by(game_id=source.id).all():
        db.session.add(Prize(game_id=clone.id, label=pr.label, sponsor=pr.sponsor, prize=pr.prize, notes=pr.notes))
    return clone

@app.route('/')
def index():
    games=Game.query.order_by(Game.created_at.desc()).limit(20).all()
    return render_template('index.html', games=games)

@app.route('/rsvp')
def rsvp_games():
    games=Game.query.filter(Game.status.in_(['rsvp','lobby'])).order_by(Game.scheduled_start_at.asc().nullslast(), Game.created_at.desc()).all()
    for g in games:
        maybe_update_schedule(g)
    db.session.commit()
    games=[g for g in games if g.status in ('rsvp','lobby')]
    return render_template('rsvp.html', games=games, list_mode=True)

@app.route('/host', methods=['GET','POST'])
@host_pin_required
def host():
    if request.method=='POST':
        tz='America/Chicago'
        start_dt=parse_local_datetime(request.form.get('scheduled_start_at'), tz)
        # RSVP opens immediately when a session is created. RSVP closes automatically when the game starts.
        rsvp_dt=None
        close_dt=None
        status='lobby' if start_dt else 'rsvp'
        g=Game(code=game_code(), title='Battle Bingo', venue=request.form.get('venue') or 'Barfly Social', starts_at=request.form.get('starts_at',''), scheduled_start_at=start_dt, rsvp_open_at=rsvp_dt, rsvp_close_at=close_dt, schedule_timezone=tz, title_image=request.form.get('title_image',''), venue_logo=request.form.get('venue_logo',''), sponsor_text=request.form.get('sponsor_text',''), countdown=int(request.form.get('countdown',10)), mark_mode=request.form.get('mark_mode','manual'), call_mode=request.form.get('call_mode','manual'), blackouts_to_win=int(request.form.get('blackouts_to_win',3)), triple_winners_needed=int(request.form.get('triple_winners_needed',1)), tv_enabled=bool(request.form.get('tv_enabled')), powers_enabled=bool(request.form.get('powers_enabled')), board_mode=request.form.get('board_mode','win'), status=status)
        db.session.add(g); db.session.commit()
        return redirect(url_for('host_game', code=g.code))
    games=Game.query.order_by(Game.created_at.desc()).all()
    now=datetime.utcnow()
    active=[g for g in games if g.status in ('started','paused','lobby','rsvp')]
    upcoming=[g for g in games if g.status=='draft']
    completed=[g for g in games if g.status in ('ended','cancelled')]
    return render_template('host.html', games=games, active=active, upcoming=upcoming, completed=completed)


@app.route('/host/<code>/duplicate', methods=['POST'])
@host_pin_required
def duplicate_game(code):
    source=Game.query.filter_by(code=code).first_or_404()
    clone=clone_game(source)
    db.session.commit()
    return redirect(url_for('host_game', code=clone.code))

@app.route('/host/<code>/delete', methods=['POST'])
@host_pin_required
def delete_game(code):
    g=Game.query.filter_by(code=code).first_or_404()
    Player.query.filter_by(game_id=g.id).delete()
    Feed.query.filter_by(game_id=g.id).delete()
    Prize.query.filter_by(game_id=g.id).delete()
    Achievement.query.filter_by(game_id=g.id).delete()
    db.session.delete(g)
    db.session.commit()
    return redirect(url_for('host'))

@app.route('/host/<code>')
@host_pin_required
def host_game(code):
    g=Game.query.filter_by(code=code).first_or_404(); maybe_auto_call(g); db.session.commit()
    return render_template('host_game.html', g=g, players=leaderboard(g.id), prizes=Prize.query.filter_by(game_id=g.id).all())

@app.route('/game/<code>')
def title(code):
    g=Game.query.filter_by(code=code).first_or_404(); maybe_update_schedule(g); db.session.commit()
    share_url=url_for('title', code=g.code, _external=True)
    return render_template('title.html', g=g, share_url=share_url)


@app.route('/qr/<code>.png')
def qr_png(code):
    """QR code is generated only for an existing saved session code."""
    g=Game.query.filter_by(code=code).first_or_404()
    join_url=url_for('title', code=g.code, _external=True)
    img=qrcode.make(join_url)
    buf=BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png', download_name=f'battle-bingo-{g.code}-qr.png')

@app.route('/host/<code>/qr')
@host_pin_required
def host_qr(code):
    g=Game.query.filter_by(code=code).first_or_404()
    join_url=url_for('title', code=g.code, _external=True)
    return render_template('qr.html', g=g, join_url=join_url)

@app.route('/game/<code>/rsvp', methods=['GET','POST'])
def rsvp(code):
    g=Game.query.filter_by(code=code).first_or_404()
    maybe_update_schedule(g); db.session.commit()
    if g.rsvp_close_at and datetime.utcnow()>=g.rsvp_close_at:
        return render_template('message.html', title='RSVP Closed', body='This game is no longer accepting RSVPs.')
    if g.status not in ('rsvp','lobby'):
        return render_template('message.html', title='RSVP Closed', body='This game is not currently accepting RSVPs. Late joins are not allowed.')
    if request.method=='POST':
        phone=clean_phone(request.form.get('phone')); name=request.form.get('name','').strip(); alias=(request.form.get('alias') or name or gen_alias()).strip()[:20]; instagram=(request.form.get('instagram') or '').strip()[:80]
        if len(phone)!=10: return render_template('message.html', title='Invalid Phone', body='Please enter a 10-digit mobile number.')
        if bad_alias(alias): alias=gen_alias()
        existing=Player.query.filter_by(game_id=g.id, phone=phone).first()
        if existing:
            session['player_id']=existing.id; return redirect(url_for('play', code=g.code, player_id=existing.id))
        aliases={p.alias.lower() for p in Player.query.filter_by(game_id=g.id).all()}
        base=alias; n=2
        while alias.lower() in aliases:
            alias=f'{base}{n}'[:20]; n+=1
        p=Player(game_id=g.id, name=name, phone=phone, alias=alias, instagram=instagram, cards_json=dump(generate_cards(g.board_mode)))
        db.session.add(p); db.session.commit(); session['player_id']=p.id
        return redirect(url_for('play', code=g.code, player_id=p.id))
    return render_template('rsvp.html', g=g)

@app.route('/my-rsvp', methods=['GET','POST'])
def my_rsvp():
    players=[]
    if request.method=='POST':
        phone=clean_phone(request.form.get('phone'))
        players=Player.query.filter_by(phone=phone).order_by(Player.created_at.desc()).all()
    return render_template('my_rsvp.html', players=players)

@app.route('/player/<code>/<int:player_id>')
@app.route('/play/<code>/<int:player_id>')
def play(code, player_id):
    g=Game.query.filter_by(code=code).first_or_404(); p=Player.query.get_or_404(player_id)
    if p.game_id!=g.id: abort(404)
    session['player_id']=p.id
    return render_template('play.html', g=g, p=p)

@app.route('/tv/<code>')
def tv(code):
    g=Game.query.filter_by(code=code).first_or_404(); return render_template('tv.html', g=g)

@app.route('/hall')
def hall():
    stats=Stat.query.order_by(Stat.wins.desc(), Stat.points.desc()).limit(100).all()
    return render_template('hall.html', stats=stats)

@app.route('/api/game/<code>')
def api_game(code):
    g=Game.query.filter_by(code=code).first_or_404(); maybe_auto_call(g); db.session.commit()
    current_label = 'GAME OVER' if g.status == 'ended' else call_label(g.current_number, g.board_mode)
    payload={'code':g.code,'title':g.title,'venue':g.venue,'status':g.status,'board_mode':g.board_mode,'current_number':g.current_number,'current_label':current_label,'called':j(g.called_json,[]),'called_labels':[call_label(n, g.board_mode) for n in j(g.called_json,[])][-20:],'countdown':game_seconds_remaining(g),'lobby_countdown':lobby_seconds_remaining(g),'lobby_paused':g.lobby_paused,'scheduled_start':format_local_datetime(g.scheduled_start_at, g.schedule_timezone),'mark_mode':g.mark_mode,'call_mode':g.call_mode,'blackouts_to_win':g.blackouts_to_win,'triple_winners_needed':g.triple_winners_needed,'power_wheel':j(g.power_wheel_json,{}),'leaderboard':game_leaderboard_payload(g),'winners':game_winners_payload(g),'feed':game_feed_payload(g)}
    payload.update(game_timer_payload(g))
    return jsonify(payload)

@app.route('/api/player/<int:pid>')
def api_player(pid):
    p=Player.query.get_or_404(pid); g=Game.query.get(p.game_id); maybe_auto_call(g); db.session.commit()
    current_label = 'GAME OVER' if g.status == 'ended' else call_label(g.current_number, g.board_mode)
    freeze_remaining=freeze_remaining_seconds(p)
    powers=sanitize_power_inventory(p)
    db.session.commit()
    payload={'id':p.id,'alias':p.alias,'code':g.code,'title':g.title,'venue':g.venue,'board_mode':g.board_mode,'board':j(p.cards_json,[]),'marked':j(p.marked_json,[]),'clovers':j(p.clovers_json,[]),'row_credit':j(p.row_credit_json,{}),'powers':powers,'used_powers':j(p.used_powers_json,[]),'points':p.points,'full_clear':p.blackouts,'clearout_place':player_clearout_place(p),'lines_left':lines_left(j(p.cards_json,[]),p),'current_number':g.current_number,'current_label':current_label,'status':g.status,'mark_mode':g.mark_mode,'called':j(g.called_json,[]),'called_labels':[call_label(n, g.board_mode) for n in j(g.called_json,[])][-20:],'countdown':game_seconds_remaining(g),'lobby_countdown':lobby_seconds_remaining(g),'lobby_paused':g.lobby_paused,'scheduled_start':format_local_datetime(g.scheduled_start_at, g.schedule_timezone),'power_wheel':j(g.power_wheel_json,{}),'winners':game_winners_payload(g),'feed':game_feed_payload(g),'leaderboard':game_leaderboard_payload(g),'frozen_number':p.frozen_number,'freeze_remaining':freeze_remaining,'fire_active':bool(p.shield) or has_power(p,'Fire'),'blocked_rows':j(p.blocked_rows_json,[])}
    payload.update(game_timer_payload(g))
    return jsonify(payload)

@app.route('/api/mark/<int:pid>', methods=['POST'])
def api_mark(pid):
    p=Player.query.get_or_404(pid); g=Game.query.get(p.game_id)
    if g.status!='started': return jsonify({'ok':False,'error':'Game not started'})
    if p.blackouts>=1: return jsonify({'ok':False,'error':'Player already cleared out'})
    if g.mark_mode!='manual': return jsonify({'ok':False,'error':'Game is in auto-mark mode'})
    n=int((request.json or {}).get('number'))
    if n not in j(g.called_json,[]): return jsonify({'ok':False,'error':'Only called spaces can be marked.'})
    ok=mark_number(p,n)
    db.session.commit(); check_end(g); db.session.commit()
    return jsonify({'ok':ok})

@app.route('/api/use_power/<int:pid>', methods=['POST'])
def api_use_power(pid):
    p=Player.query.get_or_404(pid); g=Game.query.get(p.game_id)
    if g.status!='started': return jsonify({'ok':False,'error':'Game not started'})
    if p.blackouts>=1: return jsonify({'ok':False,'error':'Player already cleared out'})
    if p.last_power_call_index==g.current_call_index: return jsonify({'ok':False,'error':'Power cooldown active until next call.'})
    name=(request.json or {}).get('name')
    held=sanitize_power_inventory(p); match=None
    normalized_request=normalize_power_name(name)
    for x in held:
        if normalize_power_name(x.get('name'))==normalized_request: match=x; break
    name=normalized_request
    if not match: return jsonify({'ok':False,'error':'Power not available'})
    result=apply_power(g,p,name)
    if result.get('ok'):
        held.remove(match); used=j(p.used_powers_json,[]); match['used_at']=now_iso(); used.append(match)
        p.powers_json=dump(held); p.used_powers_json=dump(used); p.last_power_call_index=g.current_call_index; p.points+=10
        award_achievement(p,'Power Master') if len(held)==0 and len(used)>=3 else None
    db.session.commit(); return jsonify(result)

def eligible_targets(g,p, require_power=False):
    # Battle Bingo v2 targeting: powers affect only the player directly above you.
    # If you are in first place, powers affect the player directly behind you.
    ranked=[x for x in leaderboard(g.id) if x.status=='active']
    if len(ranked) < 2:
        return []
    me_rank=next((i for i,x in enumerate(ranked) if x.id==p.id), None)
    if me_rank is None:
        return []
    target = ranked[1] if me_rank == 0 else ranked[me_rank-1]
    if target.id == p.id:
        return []
    if require_power and len(j(target.powers_json,[])) == 0:
        return []
    return [target]

def defense_check(attacker, target, power_name):
    if power_name == 'Freeze':
        if consume_power(target, 'Fire'):
            feed(attacker.game_id, f'🔥 {target.alias} auto-used Fire to block Freeze', 'power')
            return None
        # Legacy compatibility for players who activated Fire in an older build.
        if target.shield:
            target.shield=False
            feed(attacker.game_id, f'🔥 {target.alias} used Fire to negate Freeze', 'power')
            return None
    return target

def apply_power(g,p,name):
    # Compatibility for older saved inventory names from previous builds.
    if name == 'Second Chance':
        name = 'Fire'

    if name=='Recover':
        return {'ok':False,'error':'Recover is automatic. Hold it and the game will use it after you miss a called number.'}

    if name=='Fire':
        return {'ok':False,'error':'Fire is automatic. Hold it and the game will use it to block the next Freeze against you.'}

    if name=='Freeze':
        targets=eligible_targets(g,p)
        if not targets:
            return {'ok':False,'error':'No eligible target'}
        t=targets[0]
        if t.frozen_number == -1 or freeze_active(t):
            return {'ok':False,'error':f'{t.alias} already has a Freeze pending or active.'}
        t=defense_check(p, t, 'Freeze')
        if not t:
            return {'ok':True,'message':'Freeze was negated by Fire.'}
        # Freeze applies to the NEXT called number, not the current call.
        t.frozen_number=-1
        t.frozen_until_at=None
        feed(g.id, f'❄️ {p.alias} used Freeze on {t.alias}; it will hit the next call', 'power')
        return {'ok':True,'message':f'Freeze will make {t.alias} miss the entire next call unless Fire blocks it.'}

    return {'ok':False,'error':'Unknown power'}

@app.route('/host/<code>/action', methods=['POST'])
@host_pin_required
def host_action(code):
    g=Game.query.filter_by(code=code).first_or_404(); action=request.form.get('action')
    if action=='start':
        if g.status in ('rsvp','draft','lobby','paused'):
            start_game_now(g, 'Host started game')
    elif action=='delay5':
        g.scheduled_start_at=(g.scheduled_start_at or datetime.utcnow())+timedelta(minutes=5)
        feed(g.id,'⏱️ Start delayed by 5 minutes','admin')
    elif action=='lobby_pause':
        g.lobby_paused=True; feed(g.id,'⏸️ Lobby countdown paused','admin')
    elif action=='lobby_resume':
        g.lobby_paused=False; feed(g.id,'▶️ Lobby countdown resumed','admin')
    elif action=='cancel':
        g.status='cancelled'; feed(g.id,'🚫 Scheduled game cancelled','admin')
    elif action=='pause': g.status='paused'; feed(g.id,'⏸️ Game paused','admin')
    elif action=='resume': g.status='started'; g.last_call_at=datetime.utcnow(); feed(g.id,'▶️ Game resumed','admin')
    elif action=='end': g.status='ended'; feed(g.id,'🏁 GAME OVER: host ended the game','game_over'); finalize_stats(g)
    elif action=='call': call_next(g)
    elif action=='reset_session': reset_game(g, clear_players=False)
    elif action=='reset_everything': reset_game(g, clear_players=True, clear_all=True)
    db.session.commit(); return redirect(url_for('host_game', code=g.code))

@app.route('/host/<code>/alias', methods=['POST'])
@host_pin_required
def edit_alias(code):
    g=Game.query.filter_by(code=code).first_or_404(); p=Player.query.get_or_404(int(request.form['player_id']))
    if p.game_id!=g.id: abort(404)
    alias=(request.form.get('alias') or gen_alias())[:20]
    if bad_alias(alias): alias=gen_alias()
    p.alias=alias; db.session.commit()
    return redirect(url_for('host_game', code=g.code))

@app.route('/host/<code>/remove', methods=['POST'])
@host_pin_required
def remove_player(code):
    g=Game.query.filter_by(code=code).first_or_404(); p=Player.query.get_or_404(int(request.form['player_id']))
    p.status='removed'; db.session.commit()
    return redirect(url_for('host_game', code=g.code))

@app.route('/host/<code>/prize', methods=['POST'])
@host_pin_required
def add_prize(code):
    g=Game.query.filter_by(code=code).first_or_404()
    db.session.add(Prize(game_id=g.id,label=request.form.get('label','Prize'),sponsor=request.form.get('sponsor',''),prize=request.form.get('prize',''),notes=request.form.get('notes',''))); db.session.commit()
    return redirect(url_for('host_game', code=g.code))

@app.route('/host/<code>/export.csv')
@host_pin_required
def export_results(code):
    g=Game.query.filter_by(code=code).first_or_404()
    out=StringIO()
    writer=csv.writer(out)
    writer.writerow(['Rank','Alias','Name','Phone','Instagram','Points','Lines Cleared','Lines Left','Full Clears','Powers Held','Powers Used','Status'])
    for idx,p in enumerate(leaderboard(g.id), start=1):
        board=j(p.cards_json,[])
        writer.writerow([idx,p.alias,p.name,p.phone,p.instagram,p.points,len(j(p.row_credit_json,{})),lines_left(board,p),p.blackouts,len(j(p.powers_json,[])),len(j(p.used_powers_json,[])),p.status])
    filename=f'battle-bingo-{g.code}-results.csv'
    return Response(out.getvalue(), mimetype='text/csv', headers={'Content-Disposition':f'attachment; filename={filename}'})


_background_started = False
def start_background_caller():
    global _background_started
    if _background_started or os.environ.get('DISABLE_BACKGROUND_CALLER') == '1':
        return
    _background_started = True
    def loop():
        while True:
            try:
                with app.app_context():
                    ensure_schema()
                    games = Game.query.filter(Game.status.in_(['draft','rsvp','lobby','started'])).all()
                    for g in games:
                        maybe_auto_call(g)
                    db.session.commit()
                    db.session.remove()
            except Exception as exc:
                try:
                    app.logger.exception('Background caller error: %s', exc)
                except Exception:
                    pass
            time.sleep(1)
    threading.Thread(target=loop, name='battle-bingo-background-caller', daemon=True).start()

# Starts the server-side auto-call loop for Render/Gunicorn single-worker deployments.
start_background_caller()

if __name__=='__main__':
    app.run(debug=True)
