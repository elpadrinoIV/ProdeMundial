from google.appengine.ext import db
import utils
import logging

class Resultado(db.Model):
    user = db.StringProperty(required = True)
    ronda = db.StringProperty(required = True)
    resultados = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)

    @classmethod
    def by_user(cls, user, ronda = None):
        q = cls.all().filter('user =', user)
        if ronda:
            q.filter('ronda =', ronda)
        q.order("-created")
        return list(q)

    @classmethod
    def by_id(cls, resultado_id):
        return cls.get_by_id(resultado_id)


class User(db.Model):
    name = db.StringProperty(required = True)
    password_hash = db.StringProperty(required = True)
    puntaje = db.IntegerProperty(required = True)
    email = db.EmailProperty()
    celular = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add = True)

    @classmethod
    def todos(cls):
        u = cls.all()
        return u

    @classmethod
    def by_id(cls, user_id):
        return cls.get_by_id(user_id)

    @classmethod
    def by_name(cls, name):
        u = cls.all().filter('name =', name).get()
        return u

    @classmethod
    def register(cls, name, password, email = None, celular = None, puntaje = 0):
        pw_hash = utils.make_password_hash(name, password)
        u = cls(name = name, password_hash = pw_hash, puntaje = puntaje)
        if email:
            u.email = email
        if celular:
            u.celular = celular
        return u

    @classmethod
    def validate(cls, name, password):
        u = cls.by_name(name)
        if u and utils.valid_password(name, password, u.password_hash):
            return u

