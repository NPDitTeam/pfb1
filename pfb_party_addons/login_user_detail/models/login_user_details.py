# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2019-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Your Name (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

import logging
from itertools import chain
from odoo.http import request
from odoo import models, fields, api
from odoo.tools import config
_logger = logging.getLogger(__name__)
USER_PRIVATE_FIELDS = ['password']
concat = chain.from_iterable


class LoginUserDetail(models.Model):
    _inherit = 'res.users'

    @api.model
    def _check_credentials(self, password, user_agent_env):
        result = super(LoginUserDetail, self)._check_credentials(password, user_agent_env)

        # if config['proxy_mode'] and 'HTTP_X_FORWARDED_HOST' in request.httprequest.environ:
        #     ip_address = lambda self: self.headers.get('x-real-ip', self.client_address[0])
        # else:
        ip_address = request.httprequest.headers.get(' X-real-ip ', request.httprequest.remote_addr)
        # ip_address = request.httprequest.environ['REMOTE_ADDR']

        vals = {'name': self.name,
                'ip_address': ip_address
                }
        self.env['login.detail'].sudo().create(vals)
        return result


class LoginUpdate(models.Model):
    _name = 'login.detail'

    name = fields.Char(string="User Name")
    date_time = fields.Datetime(string="Login Date And Time", default=lambda self: fields.datetime.now())
    ip_address = fields.Char(string="IP Address")
