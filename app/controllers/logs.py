from flask import Blueprint
from flask_login import current_user, login_required
from flask import render_template, redirect, url_for, flash, request
from app.lib.base.provider import Provider
from app.lib.base.decorators import admin_required

bp = Blueprint('logs', __name__, url_prefix='/logs')


@bp.route('/', methods=['GET'])
@login_required
def index():
    provider = Provider()
    search = provider.search()

    results = search.search_from_request(request)

    return render_template(
        'logs/index.html',
        results=results['results'],
        params=results['params'],
        filters=results['filters']
    )
