import os, json, random, string, re, functools, threading, time
from datetime import datetime, timedelta
from urllib.parse import urljoin
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-render')
uri = os.environ.get('DATABASE_URL', 'sqlite:///battle_bingo.db')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

POWERS = ['Lucky Spot','Number Peek','Second Chance','Freeze','Row Block','Card Shuffle','Shield Breaker','Mirror Attack','Power Swap']
BAD_WORDS = {'fuck','shit','bitch','asshole','dick','pussy','cunt','nigger','faggot','slut','whore'}

class Game(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    code=db.Column(db.String(12), unique=True, index=True)
    title=db.Column(db.String(140), default='Battle Bingo')
    venue=db.Column(db.String(140), default='Barfly Social')
    starts_at=db.Column(db.String(80), default='')
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

@app.before_request
def ensure_db():
    db.create_all()

def clean_phone(p): return re.sub(r'\D','',p or '')[-10:]
def j(raw, default):
    try: return json.loads(raw or '')
    except Exception: return default
def dump(x): return json.dumps(x, separators=(',',':'))
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
def call_label(n, mode='numbers'):
    if not n: return '—'
    if mode == 'win':
        if n <= 25: return f'W-{n}'
        if n <= 50: return f'I-{n}'
        return f'N-{n}'
    return str(n)
app.jinja_env.globals['call_label']=call_label

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
    # Battle Bingo v2: one board, 25 lines x 3 numbers = 75 unique spaces.
    # numbers mode: spaces display as numbers only.
    # WIN mode: three fixed columns, W(1-25), I(26-50), N(51-75).
    if mode == 'win':
        w=list(range(1,26)); i=list(range(26,51)); n=list(range(51,76))
        random.shuffle(w); random.shuffle(i); random.shuffle(n)
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
        p.points += 5
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
        p.points += 50; times.append(now_iso())
        feed(p.game_id, f'🏆 {p.alias} achieved FULL CLEAR', 'full_clear')
        p.blackouts=new_b; p.blackout_times_json=dump(times)
        award_achievement(p,'Full Clear')

def maybe_award_line_powers(p):
    g=Game.query.get(p.game_id)
    if not g or not g.powers_enabled or (g.current_call_index or 0) < 10:
        return
    cleared=len(j(p.row_credit_json,{}))
    thresholds=set(j(p.power_cards_json,[]))
    # Award at 4, 8, 12, 16, 20, 24 cleared lines. Held inventory max = 3.
    for threshold in [4,8,12,16,20,24]:
        if cleared>=threshold and threshold not in thresholds:
            held=j(p.powers_json,[])
            if len(held)>=3:
                return
            if award_power(p, threshold):
                thresholds.add(threshold)
                p.power_cards_json=dump(list(thresholds))
            return

def award_power(p, threshold):
    g=Game.query.get(p.game_id)
    if not g or not g.powers_enabled: return False
    held=j(p.powers_json,[]); used=j(p.used_powers_json,[])
    if len(held)>=3: return False
    unavailable={x.get('name') for x in held+used if isinstance(x,dict)}
    choices=[x for x in POWERS if x not in unavailable]
    if not choices: return False
    name=random.choice(choices)
    held.append({'name':name,'earned_at':now_iso(),'used':False})
    p.powers_json=dump(held)
    g.power_wheel_json=dump({'active':True,'alias':p.alias,'power':name,'until':(datetime.utcnow()+timedelta(seconds=5)).isoformat()+'Z'})
    feed(p.game_id, f'🎁 {p.alias} earned {name}', 'power')
    if len(held)+len(used)==1: award_achievement(p,'First Blood')
    return True

def leaderboard(game_id):
    players=Player.query.filter_by(game_id=game_id, status='active').all()
    def key(p):
        board=j(p.cards_json,[])
        left=lines_left(board,p)
        times=j(p.blackout_times_json,[])
        latest=times[-1] if times else '9999-99-99T99:99:99.999Z'
        return (left, latest, -p.points)
    return sorted(players, key=key)

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

def mark_number(p, n, is_auto=False):
    g=Game.query.get(p.game_id)
    if p.frozen_number == n:
        p.frozen_number=None
        feed(p.game_id, f'❄️ {p.alias} was frozen and missed the current call', 'power')
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
    # AFK check for previous number in manual mode
    prev=g.current_number
    if prev and g.mark_mode=='manual':
        for p in Player.query.filter_by(game_id=g.id, status='active').all():
            board=j(p.cards_json,[]); marked=j(p.marked_json,[])
            if prev in all_card_nums(board) and prev not in marked and p.frozen_number != prev:
                p.afk_misses += 1
                if p.afk_misses==3:
                    feed(g.id, f'⚠️ {p.alias} may be inactive', 'afk')
    # clear row blocks each cycle
    for p in Player.query.filter_by(game_id=g.id).all():
        p.blocked_rows_json='[]'
    called=j(g.called_json,[])
    pool=j(g.call_pool_json,[])
    if not pool:
        pool=list(range(1,76)); random.shuffle(pool)
    remaining=[n for n in pool if n not in called]
    if not remaining:
        g.status='ended'
        g.current_number=None
        feed(g.id, '🏁 GAME OVER: all numbers have been called', 'game')
        finalize_stats(g)
        return
    n=remaining[0]
    called.append(n); g.current_number=n; g.current_call_index=(g.current_call_index or 0)+1
    g.called_json=dump(called); g.call_pool_json=dump(pool); g.last_call_at=datetime.utcnow()
    for pp in Player.query.filter_by(game_id=g.id, status='active').all():
        if pp.frozen_number == -1:
            pp.frozen_number = n
    # Do not write number calls to Battle Feed. Feed is player activity only.
    if g.mark_mode=='auto':
        for p in Player.query.filter_by(game_id=g.id, status='active').all():
            mark_number(p,n,is_auto=True)
    check_end(g)

def check_end(g):
    winners=Player.query.filter(Player.game_id==g.id, Player.status=='active', Player.blackouts>=1).count()
    if winners>=g.triple_winners_needed:
        g.status='ended'; feed(g.id, f'🏁 Game over: {winners} Full Clear winner(s)', 'game')
        finalize_stats(g)

def finalize_stats(g):
    if g.finalized: return
    lb=leaderboard(g.id)
    for idx,p in enumerate(lb):
        s=Stat.query.filter_by(phone=p.phone).first()
        if not s:
            s=Stat(phone=p.phone, alias=p.alias); db.session.add(s)
        s.alias=p.alias; s.games+=1; s.blackouts+=p.blackouts; s.points+=p.points
        s.powers_earned += len(j(p.powers_json,[]))+len(j(p.used_powers_json,[]))
        s.powers_used += len(j(p.used_powers_json,[]))
        if idx==0: s.wins += 1; award_achievement(p,'Battle Bingo Champion')
    g.finalized=True

def reset_game(g, clear_players=False, clear_all=False):
    g.status='rsvp'; g.rules_locked=False; g.called_json='[]'; g.call_pool_json='[]'; g.current_number=None; g.current_call_index=0; g.last_call_at=None; g.power_wheel_json='{}'; g.finalized=False
    if clear_all:
        Prize.query.filter_by(game_id=g.id).delete()
    if clear_players:
        Player.query.filter_by(game_id=g.id).delete()
    else:
        for p in Player.query.filter_by(game_id=g.id).all():
            p.cards_json=dump(generate_cards(g.board_mode)); p.marked_json='[]'; p.clovers_json='[]'; p.row_credit_json='{}'; p.power_cards_json='[]'; p.powers_json='[]'; p.used_powers_json='[]'; p.points=0; p.blackouts=0; p.blackout_times_json='[]'; p.last_power_call_index=-1; p.frozen_number=None; p.shield=False; p.mirror=False; p.blocked_rows_json='[]'; p.afk_misses=0; p.status='active'
    Feed.query.filter_by(game_id=g.id).delete()
    feed(g.id,'🗑️ Session reset','game')

@app.route('/')
def index():
    games=Game.query.order_by(Game.created_at.desc()).limit(20).all()
    return render_template('index.html', games=games)

@app.route('/host', methods=['GET','POST'])
@host_pin_required
def host():
    if request.method=='POST':
        g=Game(code=game_code(), title=request.form.get('title') or 'Battle Bingo', venue=request.form.get('venue') or 'Barfly Social', starts_at=request.form.get('starts_at',''), title_image=request.form.get('title_image',''), venue_logo=request.form.get('venue_logo',''), sponsor_text=request.form.get('sponsor_text',''), countdown=int(request.form.get('countdown',10)), mark_mode=request.form.get('mark_mode','manual'), call_mode=request.form.get('call_mode','manual'), blackouts_to_win=int(request.form.get('blackouts_to_win',3)), triple_winners_needed=int(request.form.get('triple_winners_needed',1)), tv_enabled=bool(request.form.get('tv_enabled')), powers_enabled=bool(request.form.get('powers_enabled')), board_mode=request.form.get('board_mode','numbers'))
        db.session.add(g); db.session.commit(); feed(g.id, f'🎮 {g.title} created at {g.venue}', 'game', True)
        return redirect(url_for('host_game', code=g.code))
    games=Game.query.order_by(Game.created_at.desc()).all()
    return render_template('host.html', games=games)

@app.route('/host/<code>')
@host_pin_required
def host_game(code):
    g=Game.query.filter_by(code=code).first_or_404(); maybe_auto_call(g); db.session.commit()
    return render_template('host_game.html', g=g, players=leaderboard(g.id), prizes=Prize.query.filter_by(game_id=g.id).all())

@app.route('/game/<code>')
def title(code):
    g=Game.query.filter_by(code=code).first_or_404()
    share_url=url_for('title', code=g.code, _external=True)
    return render_template('title.html', g=g, share_url=share_url)

@app.route('/game/<code>/rsvp', methods=['GET','POST'])
def rsvp(code):
    g=Game.query.filter_by(code=code).first_or_404()
    if g.status not in ('rsvp','draft'):
        return render_template('message.html', title='RSVP Closed', body='This game has already started. Late joins are not allowed.')
    if request.method=='POST':
        phone=clean_phone(request.form.get('phone')); name=request.form.get('name','').strip(); alias=(request.form.get('alias') or name or gen_alias()).strip()[:20]
        if len(phone)!=10: return render_template('message.html', title='Invalid Phone', body='Please enter a 10-digit mobile number.')
        if bad_alias(alias): alias=gen_alias()
        existing=Player.query.filter_by(game_id=g.id, phone=phone).first()
        if existing:
            session['player_id']=existing.id; return redirect(url_for('play', code=g.code, player_id=existing.id))
        aliases={p.alias.lower() for p in Player.query.filter_by(game_id=g.id).all()}
        base=alias; n=2
        while alias.lower() in aliases:
            alias=f'{base}{n}'[:20]; n+=1
        p=Player(game_id=g.id, name=name, phone=phone, alias=alias, cards_json=dump(generate_cards(g.board_mode)))
        db.session.add(p); db.session.commit(); session['player_id']=p.id; feed(g.id, f'✅ {p.alias} RSVP confirmed', 'rsvp', True)
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
    feeds=Feed.query.filter_by(game_id=g.id).order_by(Feed.id.desc()).limit(30).all()
    lb=[]
    for p in leaderboard(g.id):
        lb.append({'id':p.id,'alias':p.alias,'points':p.points,'lines_left':lines_left(j(p.cards_json,[]),p),'powers':len(j(p.powers_json,[])),'progress':len(j(p.row_credit_json,{}))%4,'rows':len(j(p.row_credit_json,{})),'afk':p.afk_misses>=3})
    current_label = 'GAME OVER' if g.status == 'ended' else call_label(g.current_number, g.board_mode)
    return jsonify({'code':g.code,'title':g.title,'venue':g.venue,'status':g.status,'board_mode':g.board_mode,'current_number':g.current_number,'current_label':current_label,'called':j(g.called_json,[]),'called_labels':[call_label(n, g.board_mode) for n in j(g.called_json,[])][-20:],'countdown':game_seconds_remaining(g),'mark_mode':g.mark_mode,'call_mode':g.call_mode,'blackouts_to_win':g.blackouts_to_win,'triple_winners_needed':g.triple_winners_needed,'power_wheel':j(g.power_wheel_json,{}),'leaderboard':lb,'feed':[{'text':f.text,'kind':f.kind} for f in feeds if f.kind!='call']})

@app.route('/api/player/<int:pid>')
def api_player(pid):
    p=Player.query.get_or_404(pid); g=Game.query.get(p.game_id); maybe_auto_call(g); db.session.commit()
    current_label = 'GAME OVER' if g.status == 'ended' else call_label(g.current_number, g.board_mode)
    return jsonify({'id':p.id,'alias':p.alias,'board_mode':g.board_mode,'board':j(p.cards_json,[]),'marked':j(p.marked_json,[]),'clovers':j(p.clovers_json,[]),'row_credit':j(p.row_credit_json,{}),'powers':j(p.powers_json,[]),'used_powers':j(p.used_powers_json,[]),'points':p.points,'full_clear':p.blackouts,'lines_left':lines_left(j(p.cards_json,[]),p),'current_number':g.current_number,'current_label':current_label,'status':g.status,'mark_mode':g.mark_mode,'called':j(g.called_json,[]),'called_labels':[call_label(n, g.board_mode) for n in j(g.called_json,[])][-20:],'countdown':game_seconds_remaining(g),'power_wheel':j(g.power_wheel_json,{}),'frozen_number':p.frozen_number,'blocked_rows':j(p.blocked_rows_json,[])})

@app.route('/api/mark/<int:pid>', methods=['POST'])
def api_mark(pid):
    p=Player.query.get_or_404(pid); g=Game.query.get(p.game_id)
    if g.status!='started': return jsonify({'ok':False,'error':'Game not started'})
    if g.mark_mode!='manual': return jsonify({'ok':False,'error':'Game is in auto-mark mode'})
    n=int((request.json or {}).get('number'))
    if n!=g.current_number: return jsonify({'ok':False,'error':'Only the exact current called space can be marked.'})
    ok=mark_number(p,n)
    db.session.commit(); check_end(g); db.session.commit()
    return jsonify({'ok':ok})

@app.route('/api/use_power/<int:pid>', methods=['POST'])
def api_use_power(pid):
    p=Player.query.get_or_404(pid); g=Game.query.get(p.game_id)
    if g.status!='started': return jsonify({'ok':False,'error':'Game not started'})
    if p.last_power_call_index==g.current_call_index: return jsonify({'ok':False,'error':'Power cooldown active until next call.'})
    name=(request.json or {}).get('name')
    held=j(p.powers_json,[]); match=None
    for x in held:
        if x.get('name')==name: match=x; break
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
    if target.mirror:
        target.mirror=False
        feed(attacker.game_id, f'🪞 {target.alias} reflected {power_name} back to {attacker.alias}', 'power')
        return attacker
    if target.shield:
        target.shield=False
        feed(attacker.game_id, f'🔄 {target.alias} blocked {power_name} with Second Chance', 'power')
        return None
    return target

def apply_power(g,p,name):
    if name=='Lucky Spot':
        board=j(p.cards_json,[]); marked=j(p.marked_json,[]); unmarked=[n for n in all_card_nums(board) if n not in marked]
        if not unmarked: return {'ok':False,'error':'No available spaces'}
        chosen=random.choice(unmarked); marked.append(chosen); clovers=j(p.clovers_json,[]); clovers.append(chosen)
        p.marked_json=dump(marked); p.clovers_json=dump(clovers); recalc_player(p,newly_marked=None)
        feed(g.id, f'🍀 {p.alias} used Lucky Spot on #{chosen}', 'power')
        return {'ok':True,'message':'Lucky Spot placed'}
    if name=='Number Peek':
        called=j(g.called_json,[]); pool=j(g.call_pool_json,[]) or list(range(1,76))
        nextn=next((n for n in pool if n not in called), None)
        feed(g.id, f'👀 {p.alias} used Number Peek', 'power')
        return {'ok':True,'message':f'Next number: {call_label(nextn)}'}
    if name=='Second Chance':
        p.shield=True; feed(g.id, f'🔄 {p.alias} activated Second Chance', 'power'); return {'ok':True}
    if name=='Mirror Attack':
        p.mirror=True; feed(g.id, f'🪞 {p.alias} armed Mirror Attack', 'power'); return {'ok':True}
    if name=='Shield Breaker':
        targets=[t for t in eligible_targets(g,p) if t.shield or t.mirror]
        if not targets: return {'ok':False,'error':'No eligible protected player'}
        t=random.choice(targets); t.shield=False; t.mirror=False; feed(g.id, f'💥 {p.alias} broke {t.alias}\'s protection', 'power'); return {'ok':True}
    if name=='Freeze':
        targets=eligible_targets(g,p)
        if not targets: return {'ok':False,'error':'No eligible target'}
        t=defense_check(p, random.choice(targets), 'Freeze')
        if not t: return {'ok':True}
        t.frozen_number = g.current_number or -1
        feed(g.id, f'❄️ {p.alias} used Freeze on {t.alias}', 'power'); return {'ok':True}
    if name=='Row Block':
        targets=eligible_targets(g,p)
        if not targets: return {'ok':False,'error':'No eligible target'}
        t=defense_check(p, random.choice(targets), 'Row Block')
        if not t: return {'ok':True}
        board=j(t.cards_json,[]); marked=set(j(t.marked_json,[])); candidates=[]
        for ri,row in enumerate(board):
            if any(n not in marked for n in row): candidates.append(str(ri))
        if candidates:
            block=random.choice(candidates); t.blocked_rows_json=dump([block]); feed(g.id, f'🚧 {p.alias} blocked one row for {t.alias}', 'power'); return {'ok':True}
        return {'ok':False,'error':'No blockable row'}
    if name=='Card Shuffle':
        targets=eligible_targets(g,p)
        if not targets: return {'ok':False,'error':'No eligible target'}
        t=defense_check(p, random.choice(targets), 'Card Shuffle')
        if not t: return {'ok':True}
        board=j(t.cards_json,[]); marked=set(j(t.marked_json,[])); unmarked=[n for n in all_card_nums(board) if n not in marked]; random.shuffle(unmarked); it=iter(unmarked)
        new=[]
        for row in board:
            nr=[]
            for n in row: nr.append(n if n in marked else next(it))
            new.append(nr)
        t.cards_json=dump(new); feed(g.id, f'🃏 {p.alias} shuffled uncalled numbers for {t.alias}', 'power'); return {'ok':True}
    if name=='Power Swap':
        targets=eligible_targets(g,p, require_power=True)
        if not targets or len(j(p.powers_json,[]))==0: return {'ok':False,'error':'No eligible power swap'}
        t=random.choice(targets); hp=j(p.powers_json,[]); tp=j(t.powers_json,[])
        a=random.choice(hp); b=random.choice(tp); hp[hp.index(a)]=b; tp[tp.index(b)]=a
        p.powers_json=dump(hp); t.powers_json=dump(tp)
        feed(g.id, f'🔄 {p.alias} swapped powers with {t.alias}', 'power'); return {'ok':True}
    return {'ok':False,'error':'Unknown power'}

@app.route('/host/<code>/action', methods=['POST'])
@host_pin_required
def host_action(code):
    g=Game.query.filter_by(code=code).first_or_404(); action=request.form.get('action')
    if action=='start':
        if g.status in ('rsvp','draft','paused'):
            g.status='started'; g.rules_locked=True; g.call_pool_json=dump(random.sample(range(1,76),75)); feed(g.id,'▶️ Game started. Rules are locked.','game')
            if not g.current_number: call_next(g)
    elif action=='pause': g.status='paused'; feed(g.id,'⏸️ Game paused','game')
    elif action=='resume': g.status='started'; g.last_call_at=datetime.utcnow(); feed(g.id,'▶️ Game resumed','game')
    elif action=='end': g.status='ended'; feed(g.id,'🏁 Game ended','game'); finalize_stats(g)
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
    p.alias=alias; db.session.commit(); feed(g.id,'🛡️ Host updated a player alias','moderation', True)
    return redirect(url_for('host_game', code=g.code))

@app.route('/host/<code>/remove', methods=['POST'])
@host_pin_required
def remove_player(code):
    g=Game.query.filter_by(code=code).first_or_404(); p=Player.query.get_or_404(int(request.form['player_id']))
    p.status='removed'; feed(g.id, f'🚫 {p.alias} was removed by host', 'moderation'); db.session.commit()
    return redirect(url_for('host_game', code=g.code))

@app.route('/host/<code>/prize', methods=['POST'])
@host_pin_required
def add_prize(code):
    g=Game.query.filter_by(code=code).first_or_404()
    db.session.add(Prize(game_id=g.id,label=request.form.get('label','Prize'),sponsor=request.form.get('sponsor',''),prize=request.form.get('prize',''),notes=request.form.get('notes',''))); db.session.commit()
    return redirect(url_for('host_game', code=g.code))


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
                    db.create_all()
                    games = Game.query.filter_by(status='started', call_mode='auto').all()
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
