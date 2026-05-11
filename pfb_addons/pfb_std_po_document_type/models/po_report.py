# -*- coding: utf-8 -*-
import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
_logger = logging.getLogger(__name__)


class POReport(models.Model):
    _inherit = "purchase.report"
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)

    def _select(self):
        return super(POReport, self)._select() + ", po.department_id"

    def _group_by(self):
        return super(POReport, self)._group_by() + ", po.department_id"