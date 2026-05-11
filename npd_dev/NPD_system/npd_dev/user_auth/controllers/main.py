# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
import base64
import odoo
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ResAuth(http.Controller):

    @http.route('/api/v1/login', type='json', methods=["POST"], auth='public', sitemap=False)
    def user_login(self, *args, **kw):
        ''' User Login API'''
        values = {}
        params = json.loads(request.httprequest.data)
        db = request.session.db or odoo.tools.config['dbfilter']
        try:
            uid = request.session.authenticate(db, params['email'], params['password'])
            request.params['login_success'] = True
            values['token'] = request.env['res.users'].sudo().get_token(params)
            values['uid'] = uid 
            values['message'] = 'User logged in successfully.'
        except odoo.exceptions.AccessDenied as e:
            if e.args == odoo.exceptions.AccessDenied().args:
                values['error'] = "Wrong email/password"
            else:
                values['error'] = e.args[0]
        return values

    @http.route('/api/v1/signup', type='json', methods=["POST"], auth='public', sitemap=False)
    def user_signup(self, *args, **kw):
        ''' User Sign API'''

        values = {}
        params = json.loads(request.httprequest.data)
        payload = { key: params.get(key) for key in ('email', 'name', 'password') }
        if not payload:
            values['error'] = 'Required: email, name and password.'
            return values
        payload['login'] = params['email']
        try:
            db, login, pwd = request.env['res.users'].sudo().signup(payload)
            request.env.cr.commit()
            uid = request.session.authenticate(db, login, pwd)
            # uid = request.env['res.users'].sudo().search([
            #     ('login', '=', payload['login'])], limit=1).id
            values['token'] = request.env['res.users'].sudo().get_token(payload)
            values['uid'] = uid
            values['message'] = 'User created successfully.'
        except Exception as err:
            values['error'] = str(err)
        return values

    @http.route('/api/v1/logout', type='json', methods=["POST"], auth='public', sitemap=False)
    def user_logout(self, *args, **kw):
        ''' User Logout API'''
        values = {}
        db = request.session.db or odoo.tools.config['dbfilter']
        headers = request.httprequest.headers
        if not headers.get('Authorization'):
            values = {'error': "Bad Request"}
            return values
        login, password = base64.b64decode(
                        headers.get('Authorization').replace('Basic ', '')).decode('utf-8').split(':')
        try:
            request.session.authenticate(db, login, password)
            request.session.logout()
            values['message'] = 'User successfully logout.'
        except Exception as err:
                values['error'] = str(err)
        return values

    @http.route('/api/v1/reset_password', type='json', auth='public', sitemap=False)
    def user_reset_password(self, *args, **kw):
        ''' User Reset Password API'''
        values = {}
        params = json.loads(request.httprequest.data)
        if params.get('email'):
            try:
                request.env['res.users'].sudo().reset_password(params.get('email'))
                values['message'] = 'Reset password link sent successfully.'
            except Exception as err:
                values['error'] = str(err)
        else:
            values['error'] = 'Required - email'
        return values

