# -*- coding: utf-8 -*-
import os
import webapp2
import jinja2
import dbmodels
from google.appengine.ext import db
from google.appengine.api import memcache
import logging
import utils
import json
import urllib2
from datetime import datetime

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)


USUARIO_ESPECIAL_RESULTADOS = "resultados_de_los_partidos"

RONDAS = [{'ronda': "Primera", 'limite': 'Thu June 14 15:00:00 2018 GMT-0000'},
          {'ronda': "Octavos", 'limite': 'Sat June 30 14:00:00 2018 GMT-0000'},
          {'ronda': "Cuartos", 'limite': 'Fri July 6 14:00:00 2018 GMT-0000'},
          {'ronda': "Semifinal", 'limite': 'Tue July 10 18:00:00 2018 GMT-0000'},
          {'ronda': "TercerPuesto", 'limite': 'Sat July 14 14:00:00 2018 GMT-0000'},
          {'ronda': "Final", 'limite': 'Sun July 15 15:00:00 2018 GMT-0000'}]
              

def getPosiciones():
    key = 'posiciones'
    usuarios_posiciones = memcache.get(key)

    if usuarios_posiciones is None:
        logging.info("getPosiciones(). 'posiciones' no esta en cache")
        usuarios_posiciones = dbmodels.User.all()
        usuarios_posiciones.order("-puntaje")
        usuarios_posiciones = list(usuarios_posiciones)
        memcache.set(key, usuarios_posiciones)
        logging.info('DB_CALL: User.all().order("-puntaje")')
    else:
        logging.info("getPosiciones(). 'posiciones' esta en cache")

    return usuarios_posiciones

def getEquipos(update = False):
    key = 'equipos'
    equipos = memcache.get(key)

    if equipos is None or update:
        logging.info("getEquipos(). 'equipos' no esta en cache")
        try:
            equiposFile = open(os.path.dirname(__file__) + '/static/data/Equipos.json')
            equipos = json.load(equiposFile)
            memcache.set(key, equipos)
        except:
            return []
    else:
        logging.info("getEquipos(). 'equipos' esta en cache")

    return equipos

def getJugadores(update = None):
    key = 'jugadores'
    jugadores = memcache.get(key)
    if jugadores is None or update:
        try:
            jugadoresFile = open(os.path.dirname(__file__) + '/static/data/Jugadores.json')
            jugadores = json.load(jugadoresFile)
            memcache.set(key, jugadores)
        except:
            return []

    return jugadores
    

def getResultado(user, ronda, update = False):
    key = 'resultado_' + ronda + "_" + user
    resultado = memcache.get(key)

    if resultado is None or update:
        logging.info("getResultado(%s, %s). '%s' no esta en cache" %(user, ronda, key))
        resultado = dbmodels.Resultado.by_user(user, ronda)
        logging.info("DB_CALL: Resultado_by_user(%s, %s)" % (user, ronda))
        if len(resultado) > 0:
            resultado = resultado[0]
            memcache.set(key, resultado)
    else:
        logging.info("getResultado(%s, %s). '%s' esta en cache" %(user, ronda, key))

    return resultado


def saveResultado(username, ronda, resultados):
    key = 'resultado_' + ronda + "_" + username
    resultado = getResultado(username, ronda)
    if resultado:
        resultado.resultados = resultados
    else:
        resultado = dbmodels.Resultado(user = username, ronda = ronda, resultados = resultados)

    resultado.put()
    memcache.set(key, resultado)


def getFixture(ronda, username = None):
    resultados = None
    if username:
        resultado = getResultado(username, ronda)
        if resultado:
            resultados = json.loads(resultado.resultados)

    fixture = {}
    try:
        fixtureFile = open(os.path.dirname(__file__) + '/static/data/' + ronda + '.json')
        fixture = json.load(fixtureFile)
    except:
        return {}


    if resultados:
        # completo con los datos llenados previamente
        for key,value in fixture.iteritems():
            for partido in value['partidos']:
                equipo1 = partido['codEquipo1']
                equipo2 = partido['codEquipo2']
                keyScore1 = ronda + "_" + equipo1 + "_vs_" + equipo2 + "_score1"
                scoreEquipo1 = resultados[keyScore1]
                keyScore2 = ronda + "_" + equipo1 + "_vs_" + equipo2 + "_score2"
                scoreEquipo2 = resultados[keyScore2]
                keyPrimerGol = ronda + "_" + equipo1 + "_vs_" + equipo2 + "_primer_gol"
                primerGol = resultados[keyPrimerGol]


                partido['scoreEquipo1'] = scoreEquipo1
                partido['scoreEquipo2'] = scoreEquipo2
                partido['primerGol'] = primerGol

    return fixture    

def getScore(user):
    user = str(user)

    score = {}

    scoreTotal = 0

    logging.info("getScore(%s)" % user)

    # extras
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
            


    #rondas
    for ronda in RONDAS:
        # traigo fixture de este user
        fixtureUser = getFixture(ronda['ronda'], user)

        # traigo resultados posta
        fixtureResultados = getFixture(ronda['ronda'], USUARIO_ESPECIAL_RESULTADOS)

        if fixtureUser != {} and fixtureResultados != {}:

            for key, value in fixtureResultados.iteritems():
                for partidoUser, partidoReal in zip(value['partidos'], fixtureUser[key]['partidos']):
                    scorePartido = 0
                    partidoUser['scoreEquipo1'] = partidoUser['scoreEquipo1'].strip()
                    partidoUser['scoreEquipo2'] = partidoUser['scoreEquipo2'].strip()
                    partidoReal['scoreEquipo1'] = partidoReal['scoreEquipo1'].strip()
                    partidoReal['scoreEquipo2'] = partidoReal['scoreEquipo2'].strip()
                    if partidoUser['scoreEquipo1'].isdigit() and partidoUser['scoreEquipo2'].isdigit() and partidoReal['scoreEquipo1'].isdigit() and partidoReal['scoreEquipo2'].isdigit():
                        # 30 puntos por acertar si ganó, empató o perdió
                        restaUser = int(partidoUser['scoreEquipo1']) - int(partidoUser['scoreEquipo2'])
                        restaReal = int(partidoReal['scoreEquipo1']) - int(partidoReal['scoreEquipo2'])
                        
                        if (restaUser < 0 and restaReal < 0) or (restaUser > 0 and restaReal > 0) or (restaUser == restaReal):
                            scorePartido += 30
                            scoreTotal += 30


                        # 15 puntos por acertar score
                        if partidoUser['scoreEquipo1'] == partidoReal['scoreEquipo1'] and partidoUser['scoreEquipo2'] == partidoReal['scoreEquipo2']:
                            scorePartido += 15
                            scoreTotal += 15

                    # 5 puntos por primer gol
                    if partidoUser['primerGol'] == partidoReal['primerGol'] and partidoReal['primerGol'] != '':
                        scorePartido += 10
                        scoreTotal += 10

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
        score = getScore(user.name)
        user.puntaje = score['scoreTotal']
        user.put()

    memcache.delete('posiciones')

########## HANDLER ##########
class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, user = self.user, **kw))

    def not_found(self):
        self.write("Not Found")


    def set_secure_cookie(self, name, val):
        cookie_val = utils.make_secure_value(val)
        self.response.headers.add_header('Set-Cookie', '%s=%s; Path=/'
                                         % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and utils.check_secure_value(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.delete_cookie('user_id')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        user_id = self.read_secure_cookie('user_id')
        self.user = user_id and dbmodels.User.by_id(int(user_id))
        logging.info("DB_CALL: User.by_id(int(%s))" % user_id)


########## BASE HANDLER ##########
class BaseHandler(Handler):
    def get(self):
        if not self.user:
            self.redirect("/login")
            return

        self.getLoggeado()

    def post(self):
        if not self.user:
            self.redirect("/login")
            return

        self.postLoggeado()

    def getLoggeado(self):
        pass

    def postLoggeado(self):
        pass

    #def getClaveTokenUsuario(self):
    #    user_id = str(self.user.key().id()).replace("-", "")
    #    return user_id + user_id


########## SIGN UP HANDLER ##########
class SignUpHandler(Handler):
    def render_page(self, **params):
        self.render("signup2.html", **params)
    
    def get(self):
        self.render_page()
        logging.info("GET_REQUEST SIGNUPHANDLER")

    def post(self):
        params = {}
        username = self.request.get("username")
        password = self.request.get("password")
        verify = self.request.get("verify")
        email = self.request.get("email")
        celular = self.request.get("celular")

        params["username"] = username
        params["email"] = email
        params["celular"] = celular

        error_en_form = False

        if not utils.valid_username_form(username):
            params["error_username"] = "Nombre de usuario invalido (no debe tener espacios)"
            error_en_form = True
        else:
            u = dbmodels.User.by_name(username)
            if u:
                params["error_username"] = "Usuario ya existe"
                error_en_form = True
                
        if not utils.valid_password_form(password):
            params["error_password"] = "Contrasena invalida"
            error_en_form = True
        elif password != verify:
            params["error_verify"] = "Las contrasenas son distintas"
            error_en_form = True

        if not utils.valid_email_form(email):
            params["error_email"] = "email invalido"
            error_en_form = True

        if not utils.valid_celular_form(celular):
            params["error_celular"] = "celular invalido"
            error_en_form = True

        if error_en_form:
            self.render_page(**params)
        else:
            user = dbmodels.User.register(username, password, email, celular)
            user.put()

            self.login(user)

            self.redirect("/")


########## LOGIN HANDLER ##########
class LoginHandler(Handler):
    def render_page(self, error = ""):
        self.render("login2.html", error_login = error)

    def get(self):
        self.render_page()
        logging.info("GET_REQUEST LOGINHANDLER")

    def post(self):
        username = self.request.get("username")
        password = self.request.get("password")
        logging.info("POST_REQUEST LOGINHANDLER (%s)" % username)

        user = dbmodels.User.validate(username, password)
        if user:
            self.login(user)
            self.redirect('/')
        else:
            error = "Usuario y contrasena invalido"
            self.render_page(error)



########## LOGOUT HANDLER ##########
class LogoutHandler(Handler):
    def get(self):
        self.response.delete_cookie('user_id')
        self.redirect('/')

########## REGLAS HANDLER ##########
class ReglasHandler(Handler):
    def get(self):
        self.render('reglas2.html')

########## POSICIONES HANDLER ##########
class PosicionesHandler(Handler):
    def get(self):
        logging.info("GET_REQUEST POSICIONESHANDLER (%s)" % self.user.name)
        usuarios = getPosiciones()

        self.render('posiciones2.html', usuarios = usuarios)

########## USUARIOS HANDLER ##########
class UsuariosHandler(Handler):
    def get(self):
        if not self.user:
            self.redirect('/')
            return
            
        if self.user.name != 'NicoDascanio' and self.user.name != 'MarianoDascanio':
            self.redirect('/')
            return

        usuarios = dbmodels.User.all()
        usuarios = list(usuarios)
        logging.info("DB_CALL: User.all())")

        self.render('usuarios.html', usuarios = usuarios)

########## MAIN PAGE HANDLER ##########
class MainPageHandler(BaseHandler):
    def getLoggeado(self):
        logging.info("GET_REQUEST MAINPAGEHANDLER (%s)" % self.user.name)
        ronda = self.request.get('ronda')

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

        fixture = getFixture(ronda['ronda'], self.user.name)

        ##score = getScore(self.user.name)
        score = 0

        mostrarExtras = False
        extras = {}

        permite_modificar = True
        limite_ronda = datetime.strptime(ronda['limite'], '%a %B %d %H:%M:%S %Y GMT-0000')
        if limite_ronda < now:
            permite_modificar = False


        if ronda['ronda'] == 'Primera':
            mostrarExtras = True
            resultado = getResultado(self.user.name, ronda['ronda'])
            if resultado:
                extras = json.loads(resultado.resultados)

            for r in RONDAS:
                if r['ronda'] == ronda:
                    ronda = r
                    break
        # now = datetime.strftime(datetime.now(), '%d/%m/%Y %H:%M')
        # now = datetime.strftime(datetime.now(), '%c')
        params = {"fixture": fixture,
                  "score": score,
                  "ronda": ronda,
                  "rondas": RONDAS,
                  "mostrarExtras": mostrarExtras,
                  "extras": extras,
                  "permite_modificar": permite_modificar,
                  "equipos": getEquipos(),
                  "jugadores": getJugadores()}

        self.render("index2.html", **params)

    def postLoggeado(self):
        logging.info("POST_REQUEST MAINPAGEHANDLER (%s)" % self.user.name)
        ronda = self.request.get('ronda')
        now = datetime.now()

        for r in RONDAS:
            if r['ronda'] == ronda:
                limite = datetime.strptime(r['limite'], '%a %B %d %H:%M:%S %Y GMT-0000')
                if limite < now:
                    self.redirect("/")
                    return

        fixture = getFixture(ronda)
        resultados = {}

        if ronda == 'Primera':
            resultados['campeon'] = self.request.get('campeon')
            resultados['segundo'] = self.request.get('segundo')
            resultados['tercero'] = self.request.get('tercero')
            resultados['cuarto'] = self.request.get('cuarto')
            resultados['bota_oro1'] = self.request.get('bota_oro1')
            resultados['bota_oro2'] = self.request.get('bota_oro2')
            resultados['balon_oro'] = self.request.get('balon_oro')
            resultados['guante_oro'] = self.request.get('guante_oro')
            resultados['fair_play'] = self.request.get('fair_play')
            resultados['goleador_argentina'] = self.request.get('goleador_argentina')
            posicion_argentina = self.request.get('posicion_argentina')
            if posicion_argentina != 'ninguno':
                resultados['posicion_argentina'] = int(posicion_argentina)
            else:
                resultados['posicion_argentina'] = posicion_argentina

        for grupo, datos_grupo in fixture.iteritems():
            for partido in datos_grupo["partidos"]:
                keyScore1 = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_score1"
                keyScore2 = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_score2"
                valueScore1 = self.request.get(keyScore1)
                valueScore2 = self.request.get(keyScore2)

                keyPrimerGol = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_primer_gol"
                valuePrimerGol = self.request.get(keyPrimerGol)

                resultados[keyScore1] = valueScore1
                resultados[keyScore2] = valueScore2
                resultados[keyPrimerGol] = valuePrimerGol

        saveResultado(self.user.name, ronda, json.dumps(resultados))
        # guardo score
        score = getScore(self.user.name)
        self.user.puntaje = score['scoreTotal']
        self.user.put()

        self.redirect("/")



########## RESULTADOS HANDLER ##########
class ResultadosHandler(BaseHandler):
    def getLoggeado(self):
        logging.info("GET_REQUEST RESULTADOSHANDLER (%s)" % self.user.name)
        ronda = self.request.get('ronda')

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

        permite_modificar = False
        if self.user.name == 'MarianoDascanio' or self.user.name == 'NicoDascanio':
            permite_modificar = True

        params = {"fixture": fixture,
                  "ronda": ronda,
                  "rondas": RONDAS,
                  "mostrarExtras": mostrarExtras,
                  "permite_modificar": permite_modificar,
                  "extras": extras,
                  "equipos": getEquipos(),
                  "jugadores": getJugadores()}
            
        #self.render("index.html", fixture = fixture, ronda = ronda, rondas = RONDAS, whoami = "resultados", mostrarExtras = mostrarExtras);
        self.render("resultados2.html", **params)

    def postLoggeado(self):
        logging.info("POST_REQUEST RESULTADOSHANDLER (%s)" % self.user.name) 
        ronda = self.request.get('ronda')
        fixture = getFixture(ronda)
        resultados = {}



        if ronda == 'Primera':
            resultados['campeon'] = self.request.get('campeon')
            resultados['segundo'] = self.request.get('segundo')
            resultados['tercero'] = self.request.get('tercero')
            resultados['cuarto'] = self.request.get('cuarto')
            resultados['bota_oro1'] = self.request.get('bota_oro1')
            resultados['bota_oro2'] = self.request.get('bota_oro2')
            resultados['balon_oro'] = self.request.get('balon_oro')
            resultados['guante_oro'] = self.request.get('guante_oro')
            resultados['fair_play'] = self.request.get('fair_play')
            resultados['goleador_argentina'] = self.request.get('goleador_argentina')
            posicion_argentina = self.request.get('posicion_argentina')
            if posicion_argentina != 'ninguno':
                resultados['posicion_argentina'] = int(posicion_argentina)
            else:
                resultados['posicion_argentina'] = posicion_argentina

        for grupo, datos_grupo in fixture.iteritems():
            for partido in datos_grupo["partidos"]:
                keyScore1 = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_score1"
                keyScore2 = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_score2"
                valueScore1 = self.request.get(keyScore1)
                valueScore2 = self.request.get(keyScore2)

                keyPrimerGol = ronda + "_" + partido["codEquipo1"] + "_vs_" + partido["codEquipo2"] + "_primer_gol"
                valuePrimerGol = self.request.get(keyPrimerGol)

                resultados[keyScore1] = valueScore1
                resultados[keyScore2] = valueScore2
                resultados[keyPrimerGol] = valuePrimerGol

        saveResultado(USUARIO_ESPECIAL_RESULTADOS, ronda, json.dumps(resultados))
        updateScores()
        self.redirect("/resultados")

########## RESULTADOS POR USUARIO HANDLER ##########
class ResultadosPorUsuarioHandler(BaseHandler):
    def getLoggeado(self):
        logging.info("GET_REQUEST RESULTADOSPORUSUARIOHANDLER (%s)" % self.user.name)
        ronda = self.request.get('ronda')

        now = datetime.now()
        if ronda:
            for r in RONDAS:
                if r['ronda'] == ronda:
                    ronda = r
                    break
        else:
            ronda = RONDAS[0]

        usuario = self.request.get('usuario')

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
            resultado = getResultado(usuario, ronda['ronda'])
            if resultado:
                extras = json.loads(resultado.resultados)

        permite_modificar = False

        usuarios = dbmodels.User.all()
        usuarios.order("name")
        usuarios = list(usuarios)

        logging.info("DB_CALL: User.all().order(name)")

        params = {"fixture": fixture,
                  "ronda": ronda,
                  "rondas": RONDAS,
                  "mostrarExtras": mostrarExtras,
                  "permite_modificar": permite_modificar,
                  "extras": extras,
                  "usuarios": usuarios,
                  "current_user": current_user,
                  "score": score,
                  "equipos": getEquipos(),
                  "jugadores": getJugadores()}
            
        #self.render("index.html", fixture = fixture, ronda = ronda, rondas = RONDAS, whoami = "resultados", mostrarExtras = mostrarExtras);
        self.render("ver_plantillas2.html", **params)

    def postLoggeado(self):
        logging.info("POST_REQUEST RESULTADOSPORUSUARIOHANDLER")
        usuario = self.request.get('usuario_seleccionado')
        self.redirect("/resultados_por_usuario?usuario=%s" % usuario)
