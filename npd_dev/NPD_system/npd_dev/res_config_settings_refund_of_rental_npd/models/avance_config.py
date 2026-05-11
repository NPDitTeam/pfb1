import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'


    refund_of_rental = fields.Boolean(string="คืนเงินประกันค่าเช่า")