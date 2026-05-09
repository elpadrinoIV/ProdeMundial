from handlers import app
from google.appengine.api import wrap_wsgi_app

app.wsgi_app = wrap_wsgi_app(app.wsgi_app)
