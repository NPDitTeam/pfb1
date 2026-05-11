from contextlib import closing

import psycopg2

import odoo
from odoo import http
from odoo.service.db import _initialize_db
from odoo.http import request
from odoo import _


class Database(http.Controller):
    @http.route('/api/saas/initialize_database', type='json', auth='none')
    def create(self, **kw):
        master_pwd = request.jsonrequest.get('master_pwd')
        name = request.jsonrequest.get('name')
        lang = request.jsonrequest.get('lang')
        password = request.jsonrequest.get('password')
        secure = odoo.tools.config.verify_admin_password(master_pwd)
        if secure:
            db = odoo.sql_db.db_connect('postgres')
            with closing(db.cursor()) as cr:
                cr.execute("SELECT datname FROM pg_database WHERE datname = %s",
                           (name,), log_exceptions=False)
                if not cr.fetchall():
                    return {'status': False, 'message': _('Database does not exist in server.')}
            if odoo.tools.config['unaccent']:
                try:
                    db = odoo.sql_db.db_connect(name)
                    with closing(db.cursor()) as cr:
                        cr.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
                        cr.commit()
                except psycopg2.Error as e:
                    return {'status': False, 'message': e}
            demo = bool(request.jsonrequest.get('demo'))
            login = request.jsonrequest.get('login')
            country_code = request.jsonrequest.get('country_code', False)
            phone = request.jsonrequest.get('phone')
            _initialize_db(id, name, demo, lang, password, login, country_code, phone)
            return {'status': True}
        return {'status': False, 'message': _('Master password is not correct.')}
