# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import base64
import io

import xlwt
from odoo import api, fields, models


class BiAccountTaxReport(models.TransientModel):
    _name = 'bi.account.tax.report'

    date_from = fields.Date('Date From', required=True)
    date_to = fields.Date('Date To', required=True)

    def print_tax_report(self):
        data = {}
        data['form'] = {
            'date_from': self.date_from,
            'date_to': self.date_to,
        }
        final_dict = {}
        final_dict.update(data)
        if self._context.get('report_type') != 'excel':
            return self.env.ref('bi_account_tax_report.action_report_account_tax').report_action(self, data=final_dict)
        else:
            filename = 'Account Tax Report.xls'
            workbook = xlwt.Workbook()
            worksheet = workbook.add_sheet('Sheet 1')
            date_format = xlwt.XFStyle()
            date_format.num_format_str = 'dd/mm/yyyy'
            style_header = xlwt.easyxf(
                "font:height 300; font: name Liberation Sans, bold on,color black; align: horiz center")
            style_table_header = xlwt.easyxf(
                "font: name Liberation Sans, bold on,color black; align: horiz center")

            worksheet.row(0).height_mismatch = True
            worksheet.row(0).height = 500
            worksheet.write_merge(0, 0, 0, 5, "Account Tax Report", style=style_header)
            worksheet.write(2, 0, 'From')
            worksheet.write(2, 1, 'To')
            worksheet.write(3, 0, self.date_from or '-', date_format)
            worksheet.write(3, 1, self.date_to or '-', date_format)
            worksheet.write(5, 0, 'Sale', style=style_table_header)
            worksheet.write(5, 1, 'Net', style=style_table_header)
            worksheet.write(5, 2, "Tax", style=style_table_header)
            lines = self.env['report.bi_account_tax_report.bi_report_account_tax'].get_lines(data['form'])
            row = 6
            col = 0
            for sale_line in lines['sale']:
                worksheet.write(row, col, sale_line.get('name'))
                worksheet.write(row, col + 1, sale_line.get('net'))
                worksheet.write(row, col + 2, sale_line.get('tax'))
                row += 1
            worksheet.write(row, col, "Purchase", style=style_table_header)
            row += 1
            for purchase_line in lines['purchase']:
                worksheet.write(row, col, purchase_line.get('name'))
                worksheet.write(row, col + 1, purchase_line.get('net'))
                worksheet.write(row, col + 2, purchase_line.get('tax'))
                row += 1

            fp = io.BytesIO()
            workbook.save(fp)

            export_id = self.env['excel.report.tax'].create(
                {'excel_file': base64.encodestring(fp.getvalue()), 'file_name': filename})
            res = {
                'view_mode': 'form',
                'res_id': export_id.id,
                'res_model': 'excel.report.tax',
                'type': 'ir.actions.act_window',
                'target': 'new'
            }
            return res
