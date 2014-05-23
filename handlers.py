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

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)


EQUIPOS={
    "teams": [
    {"group": "A", "teams": [
        {"code": "BRA", "key": "bra", "title": "Brasil"},
        {"code": "CRO", "key": "cro", "title": "Croacia"},
        {"code": "MEX", "key": "mex", "title": u'México'},
        {"code": "CMR", "key": "cmr", "title": u'Camerún'}]},
    {"group": "B", "teams": [
        {"code": "ESP", "key": "esp", "title": u'España'},
        {"code": "NED", "key": "ned", "title": "Holanda"},
        {"code": "CHI", "key": "chi", "title": "Chile"},
        {"code": "AUS", "key": "aus", "title": "Australia"}]},
    {"group": "C", "teams": [
        {"code": "COL", "key": "col", "title": "Colombia"},
        {"code": "GRE", "key": "gre", "title": "Grecia"},
        {"code": "CIV", "key": "civ", "title": "Costa de Marfil"},
        {"code": "JPN", "key": "jpn", "title": u'Japón'}]},
    {"group": "D", "teams": [
        {"code": "URU", "key": "uru", "title": "Uruguay"},
        {"code": "CRC", "key": "crc", "title": "Costa Rica"},
        {"code": "ENG", "key": "eng", "title": "Inglaterra"},
        {"code": "ITA", "key": "ita", "title": "Italia"}]},
    {"group": "E", "teams": [
        {"code": "SUI", "key": "sui", "title": "Suiza"},
        {"code": "ECU", "key": "ecu", "title": "Ecuador"},
        {"code": "FRA", "key": "fra", "title": "Francia"},
        {"code": "HON", "key": "hon", "title": "Honduras"}]},
    {"group": "F", "teams": [
        {"code": "ARG", "key": "arg", "title": "ARGENTINA"},
        {"code": "BIH", "key": "bih", "title": "Bosnia"},
        {"code": "IRN", "key": "irn", "title": u'Irán'},
        {"code": "NGA", "key": "nga", "title": "Nigeria"}]},
    {"group": "G", "teams": [
        {"code": "GER", "key": "ger", "title": "Alemania"},
        {"code": "POR", "key": "por", "title": "Portugal"},
        {"code": "GHA", "key": "gha", "title": "Ghana"},
        {"code": "USA", "key": "usa", "title": "EE.UU."}]},
    {"group": "H", "teams": [
        {"code": "RUS", "key": "rus", "title": "Rusia"},
        {"code": "BEL", "key": "bel", "title": u'Bélgica'},
        {"code": "ALG", "key": "alg", "title": "Argelia"},
        {"code": "KOR", "key": "kor", "title": "Corea del sur"}]}]
}
USUARIO_ESPECIAL_RESULTADOS = "resultados_de_los_partidos"

RONDAS = ["Primera", "Octavos", "Cuartos", "Semifinal", "TercerPuesto", "Final"]

def getGrupoDeEquipo(codigo_equipo):
    for grupo in EQUIPOS["teams"]:
        for equipo in grupo["teams"]:
            if equipo["code"] == codigo_equipo:
                return grupo["group"]

def getNombreEquipo(codigo_equipo):
    for grupo in EQUIPOS["teams"]:
        for equipo in grupo["teams"]:
            if equipo["code"] == codigo_equipo:
                return equipo["title"]


def getResultado(user, update = False):
    key = 'resultado_' + user
    resultado = memcache.get(key)

    if resultado is None or update:
        resultado = dbmodels.Resultado.by_user(user).get()
        if resultado:
            memcache.set(key, resultado)

    return resultado


def saveResultado(username, resultados):
    key = 'resultado_' + username
    resultado = getResultado(username)
    if resultado:
        resultado.resultados = resultados
    else:
        resultado = dbmodels.Resultado(user = username, resultados = resultados)

    resultado.put()
    memcache.set(key, resultado)


def getFixture(ronda, username = None):
    resultados = None
    if username:
        resultado = getResultado(username)
        if resultado:
            resultados = json.loads(resultado.resultados)

    try:
        fixtureFile = open(os.path.dirname(__file__) + '/static/data/' + ronda + '.json')
        fixture = json.load(fixtureFile)
    except:
        return {}

    if resultados:
        # completo con los datos llenados previamente
        for key,value in fixture.iteritems():
            for partido in value['partidos']:
                equipo1 = partido['equipo1']
                equipo2 = partido['equipo2']
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

    scoreTotal = 0
    for ronda in RONDAS:
        # traigo fixture de este user
        fixtureUser = getFixture(ronda, user)

        # traigo resultados posta
        fixtureResultados = getFixture(ronda, USUARIO_ESPECIAL_RESULTADOS)

        for key, value in fixtureUser.iteritems():
            for partidoUser, partidoReal in zip(value['partidos'], fixtureResultados[key]['partidos']):
                if partidoUser['scoreEquipo1'] != '' and partidoUser['scoreEquipo2'] != '' and partidoReal['scoreEquipo1'] != '' and partidoReal['scoreEquipo2'] != '':
                    # 30 puntos por acertar si ganó, empató o perdió
                    restaUser = int(partidoUser['scoreEquipo1']) - int(partidoUser['scoreEquipo2'])
                    restaReal = int(partidoReal['scoreEquipo1']) - int(partidoReal['scoreEquipo2'])
                    
                    if (restaUser < 0 and restaReal < 0) or (restaUser > 0 and restaReal > 0) or (restaUser == restaReal):
                        scoreTotal += 30

                    # 15 puntos por acertar score
                    if partidoUser['scoreEquipo1'] == partidoReal['scoreEquipo1'] and partidoUser['scoreEquipo2'] == partidoReal['scoreEquipo2']:
                        scoreTotal += 15

                # 10 puntos por primer gol
                if partidoUser['primerGol'] == partidoReal['primerGol'] and partidoReal['primerGol'] != '':
                    scoreTotal += 10

    return scoreTotal

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


########## BASE HANDLER ##########
class BaseHandler(Handler):
    def get(self):
        if not self.user:
            self.redirect("/signup")
            return

        self.getLoggeado()

    def post(self):
        if not self.user:
            self.redirect("/signup")
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
        self.render("signup.html", **params)
    
    def get(self):
        self.render_page()

    def post(self):
        params = {}
        username = self.request.get("username")
        password = self.request.get("password")
        verify = self.request.get("verify")
        email = self.request.get("email")

        params["username"] = username
        params["email"] = email

        error_en_form = False

        if not utils.valid_username_form(username):
            params["error_username"] = "Nombre de usuario invalido"
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

        if error_en_form:
            self.render_page(**params)
        else:
            user = dbmodels.User.register(username, password, email)
            user.put()

            self.login(user)

            self.redirect("/")


########## LOGIN HANDLER ##########
class LoginHandler(Handler):
    def render_page(self, error = ""):
        self.render("login.html", error_login = error)

    def get(self):
        self.render_page()

    def post(self):
        username = self.request.get("username")
        password = self.request.get("password")

        user = dbmodels.User.validate(username, password)
        if user:
            self.login(user)
            self.redirect('/')
        else:
            error = "Invalid user and pass"
            self.render_page(error)



########## LOGOUT HANDLER ##########
class LogoutHandler(Handler):
    def get(self):
        self.response.delete_cookie('user_id')
        self.redirect('/')

########## LOGOUT HANDLER ##########
class ReglasHandler(Handler):
    def get(self):
        self.render('reglas.html')

########## LOGOUT HANDLER ##########
class PosicionesHandler(Handler):
    def get(self):
        usuarios = dbmodels.User.all()
        usuarios.order("-puntaje")
        usuarios = list(usuarios)

        self.render('posiciones.html', usuarios = usuarios)


########## MAIN PAGE HANDLER ##########
class MainPageHandler(BaseHandler):
    def getLoggeado(self):
        ronda = self.request.get('ronda')
        if not ronda:
            ronda = RONDAS[0]

        fixture = getFixture(ronda, self.user.name)

        score = getScore(self.user.name)
            
        self.render("index.html", fixture = fixture, score = score, ronda = ronda, rondas = RONDAS, whoami="");

    def postLoggeado(self):
        ronda = self.request.get('ronda')
        fixture = getFixture(ronda)
        resultados = {}


        for grupo, datos_grupo in fixture.iteritems():
            for partido in datos_grupo["partidos"]:
                keyScore1 = ronda + "_" + partido["equipo1"] + "_vs_" + partido["equipo2"] + "_score1"
                keyScore2 = ronda + "_" + partido["equipo1"] + "_vs_" + partido["equipo2"] + "_score2"
                valueScore1 = self.request.get(keyScore1)
                valueScore2 = self.request.get(keyScore2)

                keyPrimerGol = ronda + "_" + partido["equipo1"] + "_vs_" + partido["equipo2"] + "_primer_gol"
                valuePrimerGol = self.request.get(keyPrimerGol)

                resultados[keyScore1] = valueScore1
                resultados[keyScore2] = valueScore2
                resultados[keyPrimerGol] = valuePrimerGol

        saveResultado(self.user.name, json.dumps(resultados))
        self.redirect("/")

########## RESULTADOS HANDLER ##########
class ResultadosHandler(BaseHandler):
    def getLoggeado(self):
        ronda = self.request.get('ronda')
        if not ronda:
            ronda = RONDAS[0]
        fixture = getFixture(ronda, USUARIO_ESPECIAL_RESULTADOS)
            
        self.render("index.html", fixture = fixture, ronda = ronda, rondas = RONDAS, whoami = "resultados");

    def postLoggeado(self):
        ronda = self.request.get('ronda')
        fixture = getFixture(ronda)
        resultados = {}

        for grupo, datos_grupo in fixture.iteritems():
            for partido in datos_grupo["partidos"]:
                keyScore1 = ronda + "_" + partido["equipo1"] + "_vs_" + partido["equipo2"] + "_score1"
                keyScore2 = ronda + "_" + partido["equipo1"] + "_vs_" + partido["equipo2"] + "_score2"
                valueScore1 = self.request.get(keyScore1)
                valueScore2 = self.request.get(keyScore2)

                keyPrimerGol = ronda + "_" + partido["equipo1"] + "_vs_" + partido["equipo2"] + "_primer_gol"
                valuePrimerGol = self.request.get(keyPrimerGol)

                resultados[keyScore1] = valueScore1
                resultados[keyScore2] = valueScore2
                resultados[keyPrimerGol] = valuePrimerGol

        saveResultado(USUARIO_ESPECIAL_RESULTADOS, json.dumps(resultados))
        self.redirect("/resultados")
