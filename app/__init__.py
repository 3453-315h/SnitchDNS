import os
import click
import datetime
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager


db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
csrf = CSRFProtect()


def create_app(config_class=None):
    # Make sure the instance path is within the ./data folder.
    data_instance_path = os.path.realpath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'data', 'instance'))

    app = Flask(__name__, instance_path=data_instance_path, instance_relative_config=True)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # First we load everything we need in order to end up with a working app.
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'snitchdns.sqlite3')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # app.config['SQLALCHEMY_ECHO'] = True
    app.config['SECRET_KEY'] = 'SnitchesGetStitches_:)'
    app.config['SESSION_COOKIE_HTTPONLY'] = True

    # And now we override any custom settings from config.py if it exists.
    app.config.from_pyfile('config.py', silent=True)

    # If we have passed any object on app creation (ie testing), override here.
    if config_class is not None:
        app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    csrf.init_app(app)

    from app.controllers.home import bp as home_bp
    app.register_blueprint(home_bp)

    from app.controllers.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.controllers.dns import bp as dns_bp
    app.register_blueprint(dns_bp)

    from app.controllers.config import bp as config_bp
    app.register_blueprint(config_bp)

    from app.controllers.logs import bp as log_bp
    app.register_blueprint(log_bp)

    from app.controllers.install import bp as install_bp
    app.register_blueprint(install_bp)

    from app.lib.base.provider import Provider

    @app.before_request
    def before_request():
        session.permanent = True
        app.permanent_session_lifetime = datetime.timedelta(minutes=20)
        session.modified = True

    @app.after_request
    def after_request(response):
        response.headers['Server'] = 'SnitchesGetStitches'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    @app.context_processor
    def processor():
        def setting_get(name, default=None):
            provider = Provider()
            return provider.settings().get(name, default)

        def is_daemon_running():
            return Provider().daemon().is_running()

        return dict(setting_get=setting_get, is_daemon_running=is_daemon_running)

    @app.cli.command('snitch_daemon', help='SnitchDNS Daemon')
    @click.option('--bind-ip', required=True, help='IP Address to bind daemon')
    @click.option('--bind-port', required=True, type=int, help='Port to bind daemon')
    def snitch_daemon(bind_ip, bind_port):
        from app.lib.daemon.cli import DNSDaemonCLI
        cli = DNSDaemonCLI()
        return cli.daemon(bind_ip, bind_port)

    @app.cli.command('snitch_env', help='This is a helper to identify the running environment')
    def snitch_env():
        print('OK')
        return True

    return app

from app.lib.models import user, config, dns
