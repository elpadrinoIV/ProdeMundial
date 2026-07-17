# -*- coding: utf-8 -*-
import os
import logging
import json
from datetime import datetime

from flask import Flask, request, redirect, render_template, make_response, g
if os.environ.get('GAE_ENV') == 'standard':
    from google.appengine.api import memcache
else:
    class _Cache:
        def __init__(self):
            self._store = {}
        def get(self, key):
            return self._store.get(key)
        def set(self, key, value, time=0):
            self._store[key] = value
        def delete(self, key):
            self._store.pop(key, None)
    memcache = _Cache()

import dbmodels
import utils

app = Flask(__name__, static_url_path='', static_folder='static')

USUARIO_ESPECIAL_RESULTADOS = "resultados_de_los_partidos"

RONDAS = [{'ronda': "Primera", 'limite': 'Thu June 11 18:55:00 2026 GMT-0000'},
          {'ronda': "16avos", 'limite': 'Sun June 28 19:00:00 2026 GMT-0000'},
          {'ronda': "Octavos", 'limite': 'Sat July 04 17:00:00 2026 GMT-0000'},
          {'ronda': "Cuartos", 'limite': 'Thu July 09 20:00:00 2026 GMT-0000'},
          {'ronda': "Semifinal", 'limite': 'Tue July 14 19:00:00 2026 GMT-0000'},
          {'ronda': "TercerPuesto", 'limite': 'Sat July 18 21:00:00 2026 GMT-0000'},
          {'ronda': "Final", 'limite': 'Sun July 19 19:00:00 2026 GMT-0000'}]


@app.before_request
def load_user():
    cookie_val = request.cookies.get('user_id')
    user_id_str = utils.check_secure_value(cookie_val) if cookie_val else None
    g.user = dbmodels.User.by_id(int(user_id_str)) if user_id_str else None


def render(template, **kw):
    return render_template(template, user=g.user, **kw)


def set_login_cookie(response, user_id):
    cookie_val = utils.make_secure_value(str(user_id))
    response.set_cookie('user_id', cookie_val, path='/')


########## CACHE HELPERS ##########

def getPosiciones():
    key = 'posiciones'
    usuarios_posiciones = memcache.get(key)
    if usuarios_posiciones is None:
        logging.info("getPosiciones(). 'posiciones' no esta en cache")
        usuarios_posiciones = dbmodels.User.all(order='-puntaje')
        memcache.set(key, usuarios_posiciones)
        logging.info('DB_CALL: User.all().order("-puntaje")')
    else:
        logging.info("getPosiciones(). 'posiciones' esta en cache")
    return usuarios_posiciones


def getEquipos(update=False):
    key = 'equipos'
    equipos = memcache.get(key)
    if equipos is None or update:
        logging.info("getEquipos(). 'equipos' no esta en cache")
        try:
            with open(os.path.join(os.path.dirname(__file__), 'static/data/Equipos.json')) as f:
                equipos = json.load(f)
            memcache.set(key, equipos)
        except Exception:
            return []
    else:
        logging.info("getEquipos(). 'equipos' esta en cache")
    return equipos


def getJugadores(update=None):
    key = 'jugadores'
    jugadores = memcache.get(key)
    if jugadores is None or update:
        try:
            with open(os.path.join(os.path.dirname(__file__), 'static/data/Jugadores.json')) as f:
                jugadores = json.load(f)
            memcache.set(key, jugadores)
        except Exception:
            return []
    return jugadores


def getResultado(user, ronda, update=False):
    key = 'resultado_' + ronda + '_' + user
    resultado = memcache.get(key)
    if resultado is None or update:
        logging.info("getResultado(%s, %s). '%s' no esta en cache" % (user, ronda, key))
        resultado_list = dbmodels.Resultado.by_user(user, ronda)
        logging.info("DB_CALL: Resultado_by_user(%s, %s)" % (user, ronda))
        if resultado_list:
            resultado = resultado_list[0]
            memcache.set(key, resultado)
        else:
            resultado = None
    else:
        logging.info("getResultado(%s, %s). '%s' esta en cache" % (user, ronda, key))
    return resultado


def saveResultado(username, ronda, resultados):
    key = 'resultado_' + ronda + '_' + username
    resultado = getResultado(username, ronda)
    if resultado:
        resultado.resultados = resultados
    else:
        resultado = dbmodels.Resultado(user=username, ronda=ronda, resultados=resultados)
    resultado.put()
    memcache.set(key, resultado)


def getFixture(ronda, username=None):
    resultados = None
    if username:
        resultado = getResultado(username, ronda)
        if resultado:
            resultados = json.loads(resultado.resultados)

    fixture = {}
    try:
        with open(os.path.join(os.path.dirname(__file__), 'static/data/' + ronda + '.json')) as f:
            fixture = json.load(f)
    except Exception:
        return {}

    if resultados:
        for key, value in fixture.items():
            for partido in value['partidos']:
                equipo1 = partido['codEquipo1']
                equipo2 = partido['codEquipo2']
                keyScore1 = ronda + "_" + equipo1 + "_vs_" + equipo2 + "_score1"
                keyScore2 = ronda + "_" + equipo1 + "_vs_" + equipo2 + "_score2"
                keyPrimerGol = ronda + "_" + equipo1 + "_vs_" + equipo2 + "_primer_gol"
                partido['scoreEquipo1'] = resultados[keyScore1]
                partido['scoreEquipo2'] = resultados[keyScore2]
                partido['primerGol'] = resultados[keyPrimerGol]

    return fixture


def getScore(user):
    user = str(user)
    score = {}
    scoreTotal = 0

    logging.info("getScore(%s)" % user)

    resultadoUser = getResultado(user, 'Primera')
    resultadoReal = getResultado(USUARIO_ESPECIAL_RESULTADOS, 'Primera')

    if resultadoUser and resultadoReal:
        resultadoUser = json.loads(resultadoUser.resultados)
        resultadoReal = json.loads(resultadoReal.resultados)

        extras = [{'campo': 'campeon', 'puntos': 100},
                  {'campo': 'segundo', 'puntos': 80},
                  {'campo': 'tercero', 'puntos': 70},
                  {'campo': 'cuarto', 'puntos': 60},
                  {'campo': 'balon_oro', 'puntos': 100},
                  {'campo': 'guante_oro', 'puntos': 100},
                  {'campo': 'fair_play', 'puntos': 50},
                  {'campo': 'goleador_argentina', 'puntos': 100},
                  {'campo': 'posicion_argentina', 'puntos': 100}]

        for extra in extras:
            if resultadoUser[extra['campo']] != 'ninguno' and resultadoUser[extra['campo']] == resultadoReal[extra['campo']]:
                scoreTotal += extra['puntos']
                score[extra['campo']] = extra['puntos']
            else:
                score[extra['campo']] = 0

        if resultadoUser['bota_oro1'] != 'ninguno' and resultadoUser['bota_oro1'] == resultadoReal['bota_oro1']:
            scoreTotal += 100
            score['bota_oro1'] = 100
        else:
            score['bota_oro1'] = 0

        if resultadoUser['bota_oro2'] != 'ninguno' and resultadoUser['bota_oro2'] == resultadoReal['bota_oro1']:
            scoreTotal += 70
            score['bota_oro2'] = 70
        else:
            score['bota_oro2'] = 0

    for ronda in RONDAS:
        fixtureUser = getFixture(ronda['ronda'], user)
        fixtureResultados = getFixture(ronda['ronda'], USUARIO_ESPECIAL_RESULTADOS)

        if fixtureUser != {} and fixtureResultados != {}:
            for key, value in fixtureResultados.items():
                for partidoUser, partidoReal in zip(value['partidos'], fixtureUser[key]['partidos']):
                    scorePartido = 0
                    partidoUser['scoreEquipo1'] = partidoUser['scoreEquipo1'].strip()
                    partidoUser['scoreEquipo2'] = partidoUser['scoreEquipo2'].strip()
                    partidoReal['scoreEquipo1'] = partidoReal['scoreEquipo1'].strip()
                    partidoReal['scoreEquipo2'] = partidoReal['scoreEquipo2'].strip()
                    if (partidoUser['scoreEquipo1'].isdigit() and partidoUser['scoreEquipo2'].isdigit()
                            and partidoReal['scoreEquipo1'].isdigit() and partidoReal['scoreEquipo2'].isdigit()):
                        restaUser = int(partidoUser['scoreEquipo1']) - int(partidoUser['scoreEquipo2'])
                        restaReal = int(partidoReal['scoreEquipo1']) - int(partidoReal['scoreEquipo2'])

                        if (restaUser < 0 and restaReal < 0) or (restaUser > 0 and restaReal > 0) or (restaUser == restaReal):
                            scorePartido += 30
                            scoreTotal += 30

                        if partidoUser['scoreEquipo1'] == partidoReal['scoreEquipo1'] and partidoUser['scoreEquipo2'] == partidoReal['scoreEquipo2']:
                            scorePartido += 15
                            scoreTotal += 15

                    if partidoUser['primerGol'] == partidoReal['primerGol'] and partidoReal['primerGol'] != '':
                        scorePartido += 5
                        scoreTotal += 5

                    if partidoUser['equipo1'] == 'ARGENTINA' or partidoUser['equipo2'] == 'ARGENTINA':
                        scoreTotal += scorePartido
                        scorePartido *= 2

                    keyScore = 'score_' + ronda['ronda'] + "_" + partidoUser['equipo1'] + "_vs_" + partidoUser['equipo2']
                    score[keyScore] = scorePartido

    score["scoreTotal"] = scoreTotal
    return score


def updateScores():
    logging.info("updateScores()")
    users = dbmodels.User.todos()
    logging.info("DB_CALL: User.todos()")
    for user in users:
        logging.info("Updating score of  (%s)" % user.name)
        score = getScore(user.name)
        user.puntaje = score['scoreTotal']
        user.put()
    memcache.delete('posiciones')


########## ROUTES ##########

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    #return redirect('/login')
    if request.method == 'GET':
        return render('signup2.html')

    params = {}
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    verify = request.form.get('verify', '')
    email = request.form.get('email', '').strip()
    celular = request.form.get('celular', '').strip()

    params['username'] = username
    params['email'] = email
    params['celular'] = celular

    error_en_form = False

    if not utils.valid_username_form(username):
        params['error_username'] = "Nombre de usuario invalido (no debe tener espacios)"
        error_en_form = True
    else:
        u = dbmodels.User.by_name(username)
        if u:
            params['error_username'] = "Usuario ya existe"
            error_en_form = True

    if not utils.valid_password_form(password):
        params['error_password'] = "Contrasena invalida"
        error_en_form = True
    elif password != verify:
        params['error_verify'] = "Las contrasenas son distintas"
        error_en_form = True

    if not utils.valid_email_form(email):
        params['error_email'] = "email invalido"
        error_en_form = True

    if not utils.valid_celular_form(celular):
        params['error_celular'] = "celular invalido"
        error_en_form = True

    if error_en_form:
        return render('signup2.html', **params)

    user = dbmodels.User.register(username, password, email, celular)
    user.put()
    resp = make_response(redirect('/'))
    set_login_cookie(resp, user.key_id)
    return resp


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        logging.info("GET_REQUEST /login")
        return render('login2.html', error_login='')

    username = request.form.get('username', '')
    password = request.form.get('password', '')
    logging.info("POST_REQUEST /login (%s)" % username)

    user = dbmodels.User.validate(username, password)
    if user:
        resp = make_response(redirect('/'))
        set_login_cookie(resp, user.key_id)
        return resp
    return render('login2.html', error_login='Usuario y contrasena invalido')


@app.route('/logout')
def logout():
    resp = make_response(redirect('/'))
    resp.delete_cookie('user_id')
    return resp


@app.route('/reglas')
def reglas():
    return render('reglas2.html')


@app.route('/posiciones')
def posiciones():
    if not g.user:
        return redirect('/')
    logging.info("GET_REQUEST /posiciones (%s)" % g.user.name)
    usuarios = getPosiciones()
    return render('posiciones2.html', usuarios=usuarios)


@app.route('/usuarios')
def usuarios():
    if not g.user:
        return redirect('/')
    if g.user.name not in ('NicoDascanio', 'MarianoDascanio'):
        return redirect('/')
    usuarios_list = dbmodels.User.all()
    logging.info("DB_CALL: User.all()")
    return render('usuarios.html', usuarios=usuarios_list)


@app.route('/', methods=['GET', 'POST'])
def index():
    if not g.user:
        return redirect('/login')

    if request.method == 'POST':
        logging.info("POST_REQUEST / (%s)" % g.user.name)
        ronda = request.form.get('ronda', '')
        now = datetime.now()

        for r in RONDAS:
            if r['ronda'] == ronda:
                limite = datetime.strptime(r['limite'], '%a %B %d %H:%M:%S %Y GMT-0000')
                if limite < now:
                    return redirect('/')

        fixture = getFixture(ronda)
        resultados = {}

        if ronda == 'Primera':
            resultados['campeon'] = request.form.get('campeon', '')
            resultados['segundo'] = request.form.get('segundo', '')
            resultados['tercero'] = request.form.get('tercero', '')
            resultados['cuarto'] = request.form.get('cuarto', '')
            resultados['bota_oro1'] = request.form.get('bota_oro1', '')
            resultados['bota_oro2'] = request.form.get('bota_oro2', '')
            resultados['balon_oro'] = request.form.get('balon_oro', '')
            resultados['guante_oro'] = request.form.get('guante_oro', '')
            resultados['fair_play'] = request.form.get('fair_play', '')
            resultados['goleador_argentina'] = request.form.get('goleador_argentina', '')
            posicion_argentina = request.form.get('posicion_argentina', 'ninguno')
            resultados['posicion_argentina'] = int(posicion_argentina) if posicion_argentina != 'ninguno' else posicion_argentina

        for grupo, datos_grupo in fixture.items():
            for partido in datos_grupo["partidos"]:
                keyScore1 = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_score1"
                keyScore2 = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_score2"
                keyPrimerGol = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_primer_gol"
                resultados[keyScore1] = request.form.get(keyScore1, '')
                resultados[keyScore2] = request.form.get(keyScore2, '')
                resultados[keyPrimerGol] = request.form.get(keyPrimerGol, '')

        saveResultado(g.user.name, ronda, json.dumps(resultados))
        score = getScore(g.user.name)
        g.user.puntaje = score['scoreTotal']
        g.user.put()
        return redirect('/')

    # GET
    logging.info("GET_REQUEST / (%s)" % g.user.name)
    ronda = request.args.get('ronda')
    now = datetime.now()
    limite = None

    if ronda:
        for r in RONDAS:
            if r['ronda'] == ronda:
                ronda = r
                limite = datetime.strptime(r['limite'], '%a %B %d %H:%M:%S %Y GMT-0000')
                break
    else:
        for r in RONDAS:
            ronda = r
            limite = datetime.strptime(r['limite'], '%a %B %d %H:%M:%S %Y GMT-0000')
            if limite > now:
                break

    ronda["diff_tiempo"] = (limite - now).total_seconds()

    fixture = getFixture(ronda['ronda'], g.user.name)
    score = 0

    mostrarExtras = False
    extras = {}

    permite_modificar = datetime.strptime(ronda['limite'], '%a %B %d %H:%M:%S %Y GMT-0000') > now

    if ronda['ronda'] == 'Primera':
        mostrarExtras = True
        resultado = getResultado(g.user.name, ronda['ronda'])
        if resultado:
            extras = json.loads(resultado.resultados)

    return render('index2.html',
                  fixture=fixture,
                  score=score,
                  ronda=ronda,
                  rondas=RONDAS,
                  mostrarExtras=mostrarExtras,
                  extras=extras,
                  permite_modificar=permite_modificar,
                  equipos=getEquipos(),
                  jugadores=getJugadores())


@app.route('/resultados', methods=['GET', 'POST'])
def resultados():
    if not g.user:
        return redirect('/login')

    if request.method == 'POST':
        logging.info("POST_REQUEST /resultados (%s)" % g.user.name)
        ronda = request.form.get('ronda', '')
        fixture = getFixture(ronda)
        resultados_data = {}

        if ronda == 'Primera':
            resultados_data['campeon'] = request.form.get('campeon', '')
            resultados_data['segundo'] = request.form.get('segundo', '')
            resultados_data['tercero'] = request.form.get('tercero', '')
            resultados_data['cuarto'] = request.form.get('cuarto', '')
            resultados_data['bota_oro1'] = request.form.get('bota_oro1', '')
            resultados_data['bota_oro2'] = request.form.get('bota_oro2', '')
            resultados_data['balon_oro'] = request.form.get('balon_oro', '')
            resultados_data['guante_oro'] = request.form.get('guante_oro', '')
            resultados_data['fair_play'] = request.form.get('fair_play', '')
            resultados_data['goleador_argentina'] = request.form.get('goleador_argentina', '')
            posicion_argentina = request.form.get('posicion_argentina', 'ninguno')
            resultados_data['posicion_argentina'] = int(posicion_argentina) if posicion_argentina != 'ninguno' else posicion_argentina

        for grupo, datos_grupo in fixture.items():
            for partido in datos_grupo["partidos"]:
                keyScore1 = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_score1"
                keyScore2 = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_score2"
                keyPrimerGol = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_primer_gol"
                resultados_data[keyScore1] = request.form.get(keyScore1, '')
                resultados_data[keyScore2] = request.form.get(keyScore2, '')
                resultados_data[keyPrimerGol] = request.form.get(keyPrimerGol, '')

        saveResultado(USUARIO_ESPECIAL_RESULTADOS, ronda, json.dumps(resultados_data))
        updateScores()
        return redirect('/resultados')

    # GET
    logging.info("GET_REQUEST /resultados (%s)" % g.user.name)
    ronda = request.args.get('ronda')
    now = datetime.now()

    if ronda:
        for r in RONDAS:
            if r['ronda'] == ronda:
                ronda = r
                break
    else:
        for r in RONDAS:
            ronda = r
            limite = datetime.strptime(r['limite'], '%a %B %d %H:%M:%S %Y GMT-0000')
            if limite > now:
                break

    fixture = getFixture(ronda['ronda'], USUARIO_ESPECIAL_RESULTADOS)

    mostrarExtras = False
    extras = {}

    if ronda['ronda'] == 'Primera':
        mostrarExtras = True
        resultado = getResultado(USUARIO_ESPECIAL_RESULTADOS, ronda['ronda'])
        if resultado:
            extras = json.loads(resultado.resultados)

    permite_modificar = g.user.name in ('MarianoDascanio', 'NicoDascanio')

    return render('resultados2.html',
                  fixture=fixture,
                  ronda=ronda,
                  rondas=RONDAS,
                  mostrarExtras=mostrarExtras,
                  permite_modificar=permite_modificar,
                  extras=extras,
                  equipos=getEquipos(),
                  jugadores=getJugadores())


@app.route('/resultados_por_usuario', methods=['GET', 'POST'])
def resultados_por_usuario():
    if not g.user:
        return redirect('/login')

    if request.method == 'POST':
        logging.info("POST_REQUEST /resultados_por_usuario")
        usuario = request.form.get('usuario_seleccionado', '')
        return redirect('/resultados_por_usuario?usuario=%s' % usuario)

    # GET
    logging.info("GET_REQUEST /resultados_por_usuario (%s)" % g.user.name)
    ronda = request.args.get('ronda')
    now = datetime.now()

    if ronda:
        for r in RONDAS:
            if r['ronda'] == ronda:
                ronda = r
                break
    else:
        ronda = RONDAS[0]

    usuario = request.args.get('usuario')
    fixture = {}
    score = None
    current_user = None

    if usuario and usuario != 'ninguno':
        fixture = getFixture(ronda['ronda'], usuario)
        current_user = usuario

        for r in RONDAS:
            if r['ronda'] == ronda['ronda']:
                limite = datetime.strptime(r['limite'], '%a %B %d %H:%M:%S %Y GMT-0000')
                if limite > now:
                    fixture = {}

        score = getScore(current_user)

    mostrarExtras = False
    extras = {}

    if ronda['ronda'] == 'Primera':
        if fixture != {}:
            mostrarExtras = True
        resultado = getResultado(usuario, ronda['ronda']) if usuario else None
        if resultado:
            extras = json.loads(resultado.resultados)

    usuarios_list = dbmodels.User.all(order='name')
    logging.info("DB_CALL: User.all().order(name)")

    return render('ver_plantillas2.html',
                  fixture=fixture,
                  ronda=ronda,
                  rondas=RONDAS,
                  mostrarExtras=mostrarExtras,
                  permite_modificar=False,
                  extras=extras,
                  usuarios=usuarios_list,
                  current_user=current_user,
                  score=score,
                  equipos=getEquipos(),
                  jugadores=getJugadores())


@app.route('/scores', methods=['GET', 'POST'])
def scores():
    if not g.user:
        return redirect('/')
    if g.user.name not in ('NicoDascanio', 'MarianoDascanio'):
        return redirect('/')

    if request.method == 'POST':
        logging.info("POST_REQUEST /scores")
        usuario = request.form.get('usuario_seleccionado', '')
        return redirect('/scores?usuario=%s' % usuario)

    usuarios_list = dbmodels.User.all(order='name')
    scores_data = {}
    usuario = request.args.get('usuario')
    if usuario:
        scores_data = getScore(usuario)

    return render('scores2.html', scores=scores_data, usuarios=usuarios_list)
