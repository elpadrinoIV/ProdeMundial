from google.cloud import datastore
import utils
import logging
import datetime

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = datastore.Client()
    return _client


class Resultado:
    KIND = 'Resultado'

    def __init__(self, entity=None, user=None, ronda=None, resultados=None):
        if entity is not None:
            self._entity = entity
        else:
            key = _get_client().key(self.KIND)
            self._entity = datastore.Entity(key=key, exclude_from_indexes=['resultados'])
            self._entity.update({
                'user': user,
                'ronda': ronda,
                'resultados': resultados,
                'created': datetime.datetime.utcnow(),
            })

    @property
    def user(self):
        return self._entity['user']

    @property
    def ronda(self):
        return self._entity['ronda']

    @property
    def resultados(self):
        return self._entity['resultados']

    @resultados.setter
    def resultados(self, value):
        self._entity['resultados'] = value

    @property
    def created(self):
        return self._entity.get('created')

    @property
    def key_id(self):
        return self._entity.key.id

    def put(self):
        _get_client().put(self._entity)

    @classmethod
    def by_user(cls, user, ronda=None):
        client = _get_client()
        q = client.query(kind=cls.KIND)
        q.add_filter('user', '=', user)
        if ronda:
            q.add_filter('ronda', '=', ronda)
        q.order = ['-created']
        return [cls(entity=e) for e in q.fetch()]

    @classmethod
    def by_id(cls, resultado_id):
        client = _get_client()
        key = client.key(cls.KIND, resultado_id)
        entity = client.get(key)
        return cls(entity=entity) if entity else None


class User:
    KIND = 'User'

    def __init__(self, entity=None, **kwargs):
        if entity is not None:
            self._entity = entity
        else:
            key = _get_client().key(self.KIND)
            self._entity = datastore.Entity(key=key)
            self._entity.update(kwargs)

    @property
    def name(self):
        return self._entity['name']

    @property
    def password_hash(self):
        return self._entity['password_hash']

    @property
    def puntaje(self):
        return self._entity.get('puntaje', 0)

    @puntaje.setter
    def puntaje(self, value):
        self._entity['puntaje'] = value

    @property
    def email(self):
        return self._entity.get('email')

    @property
    def celular(self):
        return self._entity.get('celular')

    @property
    def created(self):
        return self._entity.get('created')

    @property
    def key_id(self):
        return self._entity.key.id

    def put(self):
        _get_client().put(self._entity)

    @classmethod
    def todos(cls):
        client = _get_client()
        q = client.query(kind=cls.KIND)
        return [cls(entity=e) for e in q.fetch()]

    @classmethod
    def all(cls, order=None):
        client = _get_client()
        q = client.query(kind=cls.KIND)
        if order:
            q.order = [order]
        return [cls(entity=e) for e in q.fetch()]

    @classmethod
    def by_id(cls, user_id):
        client = _get_client()
        key = client.key(cls.KIND, user_id)
        entity = client.get(key)
        return cls(entity=entity) if entity else None

    @classmethod
    def by_name(cls, name):
        client = _get_client()
        filters = [('name', '=', name)]
        q = client.query(kind=cls.KIND, filters = filters)
        results = list(q.fetch(limit=1))
        return cls(entity=results[0]) if results else None

    @classmethod
    def register(cls, name, password, email=None, celular=None, puntaje=0):
        pw_hash = utils.make_password_hash(name, password)
        data = {
            'name': name,
            'password_hash': pw_hash,
            'puntaje': puntaje,
            'created': datetime.datetime.utcnow(),
        }
        if email:
            data['email'] = email
        if celular:
            data['celular'] = celular
        key = _get_client().key(cls.KIND)
        entity = datastore.Entity(key=key)
        entity.update(data)
        return cls(entity=entity)

    @classmethod
    def validate(cls, name, password):
        u = cls.by_name(name)
        if u and utils.valid_password(name, password, u.password_hash):
            return u
