import os, json, random, string, re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY','battle-bingo-dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL','sqlite:///battle_bingo.db').replace('postgres://','postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

POWERS = ['Lucky Spot','Number Peek','Second Chance','Freeze','Row Block','Card Shuffle','Shield Breaker','Mirror Attack','Power Swap']
BAD_WORDS = {'fuck','shit','bitch','asshole','dick','pussy','cunt','nigger','faggot','slut','whore'}

class Game(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    code=db.Column(db.String(12), unique=True, index=True)
    title=db.Column(db.String(120), default='Battle Bingo')
    venue=db.Column(db.String(120), default='Barfly Social')
    starts_at=db.Column(db.String(60), default='')
    title_image=db.Column(db.Text, default='')
    status=db.Column(db.String(20), default='rsvp') # draft/rsvp/started/paused/ended
    countdown=db.Column(db.Integer, default=10)
    mark_mode=db.Column(db.String(10), default='manual')
    blackouts_to_win=db.Column(db.Integer, default=3)
    triple_winners_needed=db.Column(db.Integer, default=1)
    tv_enabled=db.Column(db.Boolean, default=True)
    powers_enabled=db.Column(db.Boolean, default=True)
    rules_locked=db.Column(db.Boolean, default=False)
    called_json=db.Column(db.Text, default='[]')
    current_number=db.Column(db.Integer, nullable=True)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class Player(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    game_id=db.Column(db.Integer, db.ForeignKey('game.id'), index=True)
    name=db.Column(db.String(80), default='')
    phone=db.Column(db.String(20), index=True)
    alias=db.Column(db.String(40), default='Player')
    cards_json=db.Column(db.Text, default='[]')
    marked_json=db.Column(db.Text, default='[]')
    row_credit_json=db.Column(db.Text, default='{}')
    power_cards_json=db.Column(db.Text, default='[]')
    powers_json=db.Column(db.Text, default='[]')
    used_powers_json=db.Column(db.Text, default='[]')
    points=db.Column(db.Integer, default=0)
    blackouts=db.Column(db.Integer, default=0)
    blackout_times_json=db.Column(db.Text, default='[]')
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
    prize=db.Column(db.String(160))
    notes=db.Column(db.Text, default='')

class Stat(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    phone=db.Column(db.String(20), index=True)
    alias=db.Column(db.String(40))
    games=db.Column(db.Integer, default=0)
    wins=db.Column(db.Integer, default=0)
    blackouts=db.Column(db.Integer, default=0)
    points=db.Column(db.Integer, default=0)
    powers_used=db.Column(db.Integer, default=0)

def clean_phone(p): return re.sub(r'\D','',p or '')[-10:]
def j(x, default):
    try: return json.loads(x or '')
    except Exception: return default
def save_feed(game_id,text,kind='info'):
    db.session.add(Feed(game_id=game_id,text=text,kind=kind)); db.session.commit()
def code(): return ''.join(random.choices(string.ascii_uppercase+string.digits,k=6))
def bad_alias(a):
    low=re.sub(r'[^a-z0-9]','', (a or '').lower())
    return any(w in low for w in BAD_WORDS)
def gen_alias(): return random.choice(['Blue','Lucky','Silver','Green','Golden','Neon','Bayou','Royal'])+random.choice(['Tiger','Falcon','Otter','Dragon','Wolf','Clover','Ace','Wizard'])+str(random.randint(10,99))
def generate_cards():
    nums=list(range(1,76)); random.shuffle(nums)
    cards=[]
    for c in range(3):
        chunk=nums[c*25:(c+1)*25]
        cards.append([chunk[i*5:(i+1)*5] for i in range(5)])
    return cards

def rows_completed(cards, marked):
    done=[]
    ms=set(marked)
    for ci,card in enumerate(cards):
        for ri,row in enumerate(card):
            if all(n in ms for n in row): done.append(f'{ci}:{ri}')
    return done

def blackouts(cards, marked):
    ms=set(marked); return sum(1 for card in cards if all(n in ms for row in card for n in row))

def recalc_player(p, newly_marked=None):
    cards=j(p.cards_json,[]); marked=j(p.marked_json,[]); credited=set(j(p.row_credit_json,{}).keys())
    current_done=rows_completed(cards, marked)
    new_rows=[r for r in current_done if r not in credited]
    if newly_marked: p.points += 5
    for r in new_rows:
        credited.add(r); p.points += 25; save_feed(p.game_id, f'🏆 {p.alias} completed a horizontal Bingo row', 'bingo')
        ci=int(r.split(':')[0]); power_cards=set(j(p.power_cards_json,[]))
        card_rows=[x for x in credited if x.startswith(str(ci)+':')]
        if len(card_rows)>=4 and ci not in power_cards:
            award_power(p, ci)
    old_b=p.blackouts; new_b=blackouts(cards, marked)
    if new_b>old_b:
        times=j(p.blackout_times_json,[])
        for _ in range(new_b-old_b):
            p.points += 50; times.append(datetime.utcnow().isoformat(timespec='milliseconds')+'Z')
            save_feed(p.game_id, f'🔥 {p.alias} completed Blackout #{len(times)}', 'blackout')
        p.blackouts=new_b; p.blackout_times_json=json.dumps(times)
    p.row_credit_json=json.dumps({r:True for r in credited})

def award_power(p, card_index):
    held=j(p.powers_json,[]); used=j(p.used_powers_json,[]); unavailable={x['name'] for x in held+used if isinstance(x,dict)}
    choices=[x for x in POWERS if x not in unavailable]
    if choices:
        name=random.choice(choices); held.append({'name':name,'earned_at':datetime.utcnow().isoformat(timespec='seconds')+'Z','used':False})
        p.powers_json=json.dumps(held)
        pc=set(j(p.power_cards_json,[])); pc.add(card_index); p.power_cards_json=json.dumps(list(pc))
        save_feed(p.game_id, f'🎁 {p.alias} earned {name}', 'power')

def leaderboard(game_id):
    players=Player.query.filter_by(game_id=game_id).all()
    def key(p):
        times=j(p.blackout_times_json,[]); last=times[-1] if times else '9999'
        rows=len(j(p.row_credit_json,{})); marked=len(j(p.marked_json,[]))
        return (-p.blackouts,last,-p.points,-rows,-marked)
    return sorted(players,key=key)

@app.before_request
def init():
    db.create_all()

@app.route('/')
def index():
    games=Game.query.order_by(Game.created_at.desc()).all()
    return render_template('index.html', games=games)

@app.route('/host', methods=['GET','POST'])
def host():
    if request.method=='POST':
        g=Game(code=code(), title=request.form.get('title') or 'Battle Bingo', venue=request.form.get('venue') or 'Barfly Social', starts_at=request.form.get('starts_at',''), title_image=request.form.get('title_image',''), countdown=int(request.form.get('countdown',10)), mark_mode=request.form.get('mark_mode','manual'), blackouts_to_win=int(request.form.get('blackouts_to_win',3)), triple_winners_needed=int(request.form.get('triple_winners_needed',1)), status='rsvp')
        db.session.add(g); db.session.commit(); save_feed(g.id, f'🎮 {g.title} created at {g.venue}', 'game')
        return redirect(url_for('host_game', code=g.code))
    games=Game.query.order_by(Game.created_at.desc()).all()
    return render_template('host.html', games=games)

@app.route('/host/<code>')
def host_game(code):
    g=Game.query.filter_by(code=code).first_or_404()
    return render_template('host_game.html', g=g, players=leaderboard(g.id), prizes=Prize.query.filter_by(game_id=g.id).all())

@app.route('/game/<code>')
def title(code):
    g=Game.query.filter_by(code=code).first_or_404()
    return render_template('title.html', g=g)

@app.route('/game/<code>/rsvp', methods=['GET','POST'])
def rsvp(code):
    g=Game.query.filter_by(code=code).first_or_404()
    if g.status not in ('rsvp','draft'): return render_template('message.html', title='RSVP Closed', body='This game has already started. Late joins are not allowed.')
    if request.method=='POST':
        phone=clean_phone(request.form.get('phone'))
        name=request.form.get('name','').strip()
        alias=(request.form.get('alias') or name or gen_alias()).strip()[:20]
        if len(phone)!=10: return render_template('message.html', title='Invalid Phone', body='Please enter a 10-digit mobile number.')
        if bad_alias(alias): alias=gen_alias()
        existing=Player.query.filter_by(game_id=g.id, phone=phone).first()
        if existing:
            session['player_id']=existing.id; return redirect(url_for('play', code=g.code, player_id=existing.id))
        aliases={p.alias.lower() for p in Player.query.filter_by(game_id=g.id).all()}
        base=alias; n=2
        while alias.lower() in aliases:
            alias=f'{base}{n}'; n+=1
        p=Player(game_id=g.id, name=name, phone=phone, alias=alias, cards_json=json.dumps(generate_cards()))
        db.session.add(p); db.session.commit(); session['player_id']=p.id
        save_feed(g.id, f'✅ {p.alias} RSVP confirmed', 'rsvp')
        return redirect(url_for('play', code=g.code, player_id=p.id))
    return render_template('rsvp.html', g=g)

@app.route('/my-rsvp', methods=['GET','POST'])
def my_rsvp():
    players=[]
    if request.method=='POST':
        phone=clean_phone(request.form.get('phone'))
        players=Player.query.filter_by(phone=phone).order_by(Player.created_at.desc()).all()
    return render_template('my_rsvp.html', players=players)

@app.route('/play/<code>/<int:player_id>')
def play(code, player_id):
    g=Game.query.filter_by(code=code).first_or_404(); p=Player.query.get_or_404(player_id)
    if p.game_id!=g.id: abort(404)
    session['player_id']=p.id
    return render_template('play.html', g=g, p=p)

@app.route('/tv/<code>')
def tv(code):
    g=Game.query.filter_by(code=code).first_or_404(); return render_template('tv.html', g=g)

@app.route('/api/game/<code>')
def api_game(code):
    g=Game.query.filter_by(code=code).first_or_404()
    feeds=Feed.query.filter_by(game_id=g.id).order_by(Feed.id.desc()).limit(20).all()
    lb=[]
    for p in leaderboard(g.id):
        lb.append({'alias':p.alias,'points':p.points,'blackouts':p.blackouts,'powers':len(j(p.powers_json,[])),'progress':len(j(p.row_credit_json,{}))%4,'rows':len(j(p.row_credit_json,{}))})
    return jsonify({'code':g.code,'title':g.title,'venue':g.venue,'status':g.status,'current_number':g.current_number,'called':j(g.called_json,[]),'leaderboard':lb,'feed':[{'text':f.text,'kind':f.kind} for f in feeds]})

@app.route('/api/player/<int:pid>')
def api_player(pid):
    p=Player.query.get_or_404(pid); g=Game.query.get(p.game_id)
    return jsonify({'alias':p.alias,'cards':j(p.cards_json,[]),'marked':j(p.marked_json,[]),'row_credit':j(p.row_credit_json,{}),'powers':j(p.powers_json,[]),'used_powers':j(p.used_powers_json,[]),'points':p.points,'blackouts':p.blackouts,'current_number':g.current_number,'status':g.status,'mark_mode':g.mark_mode,'called':j(g.called_json,[])})

@app.route('/api/mark/<int:pid>', methods=['POST'])
def api_mark(pid):
    p=Player.query.get_or_404(pid); g=Game.query.get(p.game_id)
    n=int(request.json.get('number'))
    if g.status!='started': return jsonify({'ok':False,'error':'Game not started'})
    if n!=g.current_number: return jsonify({'ok':False,'error':'Only the current called number can be marked.'})
    marked=j(p.marked_json,[])
    if n not in marked:
        marked.append(n); p.marked_json=json.dumps(marked); p.afk_misses=0; recalc_player(p,newly_marked=n); db.session.commit()
    return jsonify({'ok':True})

@app.route('/api/use_power/<int:pid>', methods=['POST'])
def use_power(pid):
    p=Player.query.get_or_404(pid); g=Game.query.get(p.game_id)
    name=request.json.get('name')
    held=j(p.powers_json,[]); match=None
    for x in held:
        if x.get('name')==name: match=x; break
    if not match: return jsonify({'ok':False,'error':'Power not available'})
    held.remove(match); used=j(p.used_powers_json,[]); used.append(match); p.powers_json=json.dumps(held); p.used_powers_json=json.dumps(used); p.points+=10
    if name=='Lucky Spot':
        cards=j(p.cards_json,[]); marked=j(p.marked_json,[]); unmarked=[n for card in cards for row in card for n in row if n not in marked]
        if unmarked:
            chosen=random.choice(unmarked); marked.append(chosen); p.marked_json=json.dumps(marked); save_feed(g.id, f'🍀 {p.alias} used Lucky Spot on #{chosen}', 'power')
    else:
        save_feed(g.id, f'⚡ {p.alias} used {name}', 'power')
    recalc_player(p); db.session.commit(); return jsonify({'ok':True})

@app.route('/host/<code>/action', methods=['POST'])
def host_action(code):
    g=Game.query.filter_by(code=code).first_or_404(); action=request.form.get('action')
    if action=='start':
        g.status='started'; g.rules_locked=True; save_feed(g.id,'▶️ Game started. Rules are locked.','game')
    elif action=='pause': g.status='paused'; save_feed(g.id,'⏸️ Game paused','game')
    elif action=='resume': g.status='started'; save_feed(g.id,'▶️ Game resumed','game')
    elif action=='end': g.status='ended'; save_feed(g.id,'🏁 Game ended','game'); finalize_stats(g)
    elif action=='call': call_next(g)
    elif action=='reset_session': reset_game(g, keep_players=False)
    elif action=='reset_everything': reset_game(g, keep_players=False, all_data=True)
    db.session.commit(); return redirect(url_for('host_game', code=g.code))

def call_next(g):
    if g.status!='started': return
    called=j(g.called_json,[]); remaining=[n for n in range(1,76) if n not in called]
    if not remaining: g.status='ended'; return
    n=random.choice(remaining); called.append(n); g.current_number=n; g.called_json=json.dumps(called); save_feed(g.id, f'📣 Number called: {n}', 'call')
    if g.mark_mode=='auto':
        for p in Player.query.filter_by(game_id=g.id, status='active').all():
            cards=j(p.cards_json,[]); allnums=[x for card in cards for row in card for x in row]
            marked=j(p.marked_json,[])
            if n in allnums and n not in marked:
                marked.append(n); p.marked_json=json.dumps(marked); recalc_player(p,newly_marked=n)
    check_end(g)

def check_end(g):
    winners=Player.query.filter(Player.game_id==g.id, Player.blackouts>=3).count()
    if winners>=g.triple_winners_needed:
        g.status='ended'; save_feed(g.id, f'🏁 Game over: {winners} triple blackout winner(s)', 'game'); finalize_stats(g)

def finalize_stats(g):
    if getattr(g,'_finalized',False): return
    lb=leaderboard(g.id)
    for i,p in enumerate(lb):
        s=Stat.query.filter_by(phone=p.phone).first() or Stat(phone=p.phone, alias=p.alias)
        if not s.id: db.session.add(s)
        s.alias=p.alias; s.games+=1; s.blackouts+=p.blackouts; s.points+=p.points; s.powers_used+=len(j(p.used_powers_json,[]))
        if i==0: s.wins+=1
    db.session.commit()

def reset_game(g, keep_players=False, all_data=False):
    g.status='rsvp'; g.rules_locked=False; g.called_json='[]'; g.current_number=None
    if all_data or not keep_players:
        Player.query.filter_by(game_id=g.id).delete(); Feed.query.filter_by(game_id=g.id).delete()
    save_feed(g.id,'🗑️ Session reset','game')

@app.route('/host/<code>/alias', methods=['POST'])
def edit_alias(code):
    g=Game.query.filter_by(code=code).first_or_404(); p=Player.query.get_or_404(int(request.form['player_id']))
    alias=request.form.get('alias') or gen_alias()
    if bad_alias(alias): alias=gen_alias()
    p.alias=alias[:20]; db.session.commit(); save_feed(g.id, f'🛡️ Host updated a player alias', 'moderation')
    return redirect(url_for('host_game', code=g.code))

@app.route('/host/<code>/prize', methods=['POST'])
def add_prize(code):
    g=Game.query.filter_by(code=code).first_or_404()
    db.session.add(Prize(game_id=g.id,label=request.form.get('label','Prize'),sponsor=request.form.get('sponsor',''),prize=request.form.get('prize',''),notes=request.form.get('notes',''))); db.session.commit()
    return redirect(url_for('host_game', code=g.code))

@app.route('/hall')
def hall():
    stats=Stat.query.order_by(Stat.wins.desc(), Stat.points.desc()).limit(50).all()
    return render_template('hall.html', stats=stats)

if __name__=='__main__': app.run(debug=True)
