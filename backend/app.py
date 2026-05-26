from flask import Flask, send_from_directory
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import Config
from models import db
from mail_config import init_mail
from celery_config import create_celery
from cache_config import init_cache
import os

from routes.auth    import auth_bp
from routes.admin   import admin_bp
from routes.doctor  import doctor_bp
from routes.patient import patient_bp


def create_app():
    app = Flask(
        __name__,
        static_folder  = os.path.join(os.path.dirname(__file__), '..', 'frontend'),
        static_url_path= ''
    )

    app.config.from_object(Config)

    db.init_app(app)
    JWTManager(app)
    CORS(app)
    init_mail(app)
    init_cache(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(patient_bp)

    @app.route('/')
    def home():
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/<path:filename>')
    def serve_file(filename):
        return send_from_directory(app.static_folder, filename)

    return app


app    = create_app()
celery = create_celery(app)

import tasks


if __name__ == '__main__':
    app.run(debug=True)