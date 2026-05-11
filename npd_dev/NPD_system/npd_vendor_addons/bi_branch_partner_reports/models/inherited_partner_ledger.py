# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import base64
import io

import xlwt
from odoo import api, fields, models


class AccountingReportPartnerLedger(models.TransientModel):
    _inherit = 'accounting_report.partner_ledger'

    branch_ids = fields.Many2many('res.branch', string="Branch")

    def print_partner_ledger(self):

        data = {}
        data['computed'] = {}
        
        obj_partner = self.env['res.partner']
        used_context = {'lang': 'en_US', 'strict_range': True, 'date_from': self.date_from,
                        'journal_ids': [a.id for a in self.journal_ids], 'date_to': self.date_to,
                        'state': self.target_move, 'reconciled': self.reconciled,'branch_ids':[branch.id for branch in self.branch_ids]
                        
                        }
        query_get_data = self.env['account.move.line'].with_context(used_context)._query_get()
        data['computed']['move_state'] = ['draft', 'posted']
        if self.target_move == 'posted':
            data['computed']['move_state'] = ['posted']
        result_selection = self.result_selection
        if result_selection == 'supplier':
            data['computed']['ACCOUNT_TYPE'] = ['payable']
        elif result_selection == 'customer':
            data['computed']['ACCOUNT_TYPE'] = ['receivable']
        else:
            data['computed']['ACCOUNT_TYPE'] = ['payable', 'receivable']

        self.env.cr.execute("""
                    SELECT a.id
                    FROM account_account a
                    WHERE a.internal_type IN %s
                    AND NOT a.deprecated""", (tuple(data['computed']['ACCOUNT_TYPE']),))
        data['computed']['account_ids'] = [a for (a,) in self.env.cr.fetchall()]
        params = [tuple(data['computed']['move_state']), tuple(data['computed']['account_ids'])] + query_get_data[2]
        reconcile_clause = "" if self.reconciled else ' AND "account_move_line".full_reconcile_id IS NULL '
        query = """
                    SELECT DISTINCT "account_move_line".partner_id
                    FROM """ + query_get_data[0] + """, account_account AS account, account_move AS am
                    WHERE "account_move_line".partner_id IS NOT NULL
                        AND "account_move_line".account_id = account.id
                        AND am.id = "account_move_line".move_id
                        AND am.state IN %s
                        AND "account_move_line".account_id IN %s
                        AND NOT account.deprecated
                        AND """ + query_get_data[1] + reconcile_clause
        self.env.cr.execute(query, tuple(params))
        partner_ids = [res['partner_id'] for res in self.env.cr.dictfetchall()]
        partners = obj_partner.browse(partner_ids)
        partners = sorted(partners, key=lambda x: (x.ref or '', x.name or ''))
        docs = partners
        final_docs = [a.id for a in docs]
        branch_name = [branch.name for branch in self.branch_ids]
        final_dict = {
            'data': data,
            'docs': final_docs,
            'partner_ids': partner_ids,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'target_move': self.target_move,
            'amount_currency': self.amount_currency,
            'branchs': branch_name,
        }
        if self._context.get('report_type') != 'excel':
            return self.env.ref('bi_partner_ledger_report.bi_report_partnerledger_action').with_context(
                used_context).report_action(self, data=final_dict)
        else:
            filename = 'Partner Ledger.xls'
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
            worksheet.write_merge(0, 0, 0, 5, "Partner Ledger Report", style=style_header)
            worksheet.write(2, 0, 'Target Move')
            worksheet.write(2, 1, 'Start Date')
            worksheet.write(2, 2, 'End Date')
            worksheet.write(2, 3, 'Branch')
            worksheet.write(3, 0, 'All Posted Entries' if self.target_move == 'posted' else 'All Entries')
            worksheet.write(3, 1, self.date_from or '-', date_format)
            worksheet.write(3, 2, self.date_to or '-', date_format)
            worksheet.write(3, 3, [branch.name+',' for branch in self.branch_ids])
            worksheet.write(5, 0, 'Date')
            worksheet.write(5, 1, 'JRNL')
            worksheet.write(5, 2, 'Account')
            worksheet.write(5, 3, 'Ref')
            worksheet.write(5, 4, 'Debit')
            worksheet.write(5, 5, 'Credit')
            worksheet.write(5, 6, 'Balance')
            row = 6
            col = 0
            for partner in docs:
                worksheet.write(row, col,partner.name, style=style_table_header)
                debit = self.env['report.bi_partner_ledger_report.bi_report_partnerledger'].with_context(
                    reconciled=self.reconciled, used_context=used_context)._sum_partner(final_dict['data'], partner,
                                                                                        'debit')
                credit = self.env['report.bi_partner_ledger_report.bi_report_partnerledger'].with_context(
                    reconciled=self.reconciled, used_context=used_context)._sum_partner(final_dict['data'], partner,
                                                                                        'credit')
                balance = self.env['report.bi_partner_ledger_report.bi_report_partnerledger'].with_context(
                    reconciled=self.reconciled, used_context=used_context)._sum_partner(final_dict['data'], partner,
                                                                                        'debit - credit')
                worksheet.write(row, col + 4, debit, style=style_table_header)
                worksheet.write(row, col + 5, credit, style=style_table_header)
                worksheet.write(row, col + 6, balance, style=style_table_header)
                row += 1
                for line in self.env['report.bi_partner_ledger_report.bi_report_partnerledger'].with_context(
                        reconciled=self.reconciled, used_context=used_context)._lines(final_dict['data'], partner):
                    worksheet.write(row, col, line['date'], date_format)
                    worksheet.write(row, col + 1, line['code'])
                    worksheet.write(row, col + 2, line['a_code'])
                    worksheet.write(row, col + 3, line['displayed_name'])
                    worksheet.write(row, col + 4, line['debit'])
                    worksheet.write(row, col + 5, line['credit'])
                    worksheet.write(row, col + 6, line['progress'])
                    row += 1

            fp = io.BytesIO()
            workbook.save(fp)

            export_id = self.env['excel.report'].create(
                {'excel_file': base64.encodestring(fp.getvalue()), 'file_name': filename})
            res = {
                'view_mode': 'form',
                'res_id': export_id.id,
                'res_model': 'excel.report',
                'view_type': 'form',
                'type': 'ir.actions.act_window',
                'target': 'new'
            }
            return res
