import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'


    fleet_refund = fields.Boolean(string="คืนเงินโอนเกิน/คืนหัก ณ ที่จ่าย")