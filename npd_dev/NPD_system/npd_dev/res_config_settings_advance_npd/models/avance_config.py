import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    advance_re_approve_show = fields.Boolean(string="Show Approve Advance Request")
    avance_cl_approve_show = fields.Boolean(string="Show Approve Avance Clear")
    # refund_of_rental = fields.Boolean(string="คืนเงินประกันค่าเช่า")