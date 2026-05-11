# -*- coding: utf-8 -*-

from odoo import api, models,tools, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class report_stock(models.Model):
    _inherit = 'stock.picking'

    def get_sale_person(self,source_document):
        order = self.env['sale.order'].search([('name', '=', source_document)])
        name = ' - '
        if order:
            name = order[0].user_id.name

        return name
