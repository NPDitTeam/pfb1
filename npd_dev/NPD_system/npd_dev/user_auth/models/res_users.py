# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import requests
import logging
from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class ResUser(models.Model):
    _inherit = 'res.users'

    @classmethod
    def get_token(cls, params):
        auth = requests.auth._basic_auth_str(
            params['email'], params['password'])
        return auth
