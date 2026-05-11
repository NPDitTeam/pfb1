# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ExcelReportTax(models.TransientModel):
    _name = "excel.report.tax"

    excel_file = fields.Binary('Excel Report')
    file_name = fields.Char('Excel File', size=64)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: