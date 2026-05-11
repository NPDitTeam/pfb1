import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'


    lock_rent = fields.Boolean(string="ล็อกวันที่เช่า/วันที่ชำระ")