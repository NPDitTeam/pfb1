# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
import xlwt
import base64
import io
from odoo.exceptions import UserError

class AccountingReportBi(models.TransientModel):
	_inherit = "accounting.report.bi"

	
	def _print_excel(self,report_lines,report_name):
		if report_name == 'balance_sheet':
			return self._print_balance_sheet_excel_report(report_lines)
		elif report_name == 'general_ledger':
			return self._print_general_ledger_excel_report(report_lines)
		elif report_name == 'trial_balance':
			return self._print_trial_balance_excel_report(report_lines)
		else:
			raise UserError('Misconfiguration. Please Update module.\n There is no any associated report.')

	def _print_balance_sheet_excel_report(self,report_lines):
		filename = self.account_report_id.name
		filename += '.xls'
		workbook = xlwt.Workbook()
		worksheet = workbook.add_sheet('Sheet 1')
		date_format = xlwt.XFStyle()
		date_format.num_format_str = 'dd/mm/yyyy'
		style_header = xlwt.easyxf(
			"font:height 300; font: name Liberation Sans, bold on,color black; align: horiz center")
		worksheet.row(0).height_mismatch = True
		worksheet.row(0).height = 500
		worksheet.write_merge(0, 0, 0, 5, self.account_report_id.name + " Report", style=style_header)
		worksheet.write(2,0,'Target Move')
		if self.date_from:
			worksheet.write(2,1,'Start Date')
		if self.date_to:
			worksheet.write(2,2,'End Date')
		worksheet.write(3,0,'All Posted Entries' if self.target_move == 'posted' else 'All Entries')
		if self.date_from:
			worksheet.write(3,1,self.date_from,date_format)
		if self.date_to:
			worksheet.write(3,2,self.date_to,date_format)
		if self.debit_credit:
			worksheet.write(5, 0, 'Name')
			worksheet.write(5, 1, 'Debit')
			worksheet.write(5, 2, 'Credit')
			worksheet.write(5, 3, 'Balance')
			row = 6
			col = 0
			for lines in report_lines:
				if lines.get('level') != 0:
					if lines.get('level') > 3:
						style_line = xlwt.easyxf(
							"font:bold off,color black;")
					else:
						style_line = xlwt.easyxf(
							"font:bold on,color black;")
					worksheet.write(row, col, lines.get('name'),style_line)
					worksheet.write(row, col+1, lines.get('debit'),style_line)
					worksheet.write(row, col+2, lines.get('credit'),style_line)
					worksheet.write(row, col+3, lines.get('balance'),style_line)
					row += 1
		elif not self.enable_filter and not self.debit_credit:
			worksheet.write(5, 0, 'Name')
			worksheet.write(5, 1, 'Balance')
			row = 6
			col = 0
			for lines in report_lines:
				if lines.get('level') != 0:
					if lines.get('level') > 3:
						style_line = xlwt.easyxf(
							"font:bold off,color black;")
					else:
						style_line = xlwt.easyxf(
							"font:bold on,color black;")
					worksheet.write(row, col, lines.get('name'), style_line)
					worksheet.write(row, col + 1, lines.get('balance'), style_line)
					row += 1
		else:
			worksheet.write(5, 0, 'Name')
			worksheet.write(5, 1, 'Balance')
			worksheet.write(5, 2, self.label_filter)
			row = 6
			col = 0
			for lines in report_lines:
				if lines.get('level') != 0:
					if lines.get('level') > 3:
						style_line = xlwt.easyxf(
							"font:bold off,color black;")
					else:
						style_line = xlwt.easyxf(
							"font:bold on,color black;")
					worksheet.write(row, col, lines.get('name'), style_line)
					worksheet.write(row, col + 1, lines.get('balance'), style_line)
					worksheet.write(row, col + 2, lines.get('balance_cmp'), style_line)
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

	def check_report(self):
		res = super(AccountingReportBi, self).check_report()
		if self._context.get('report_type') == 'excel':
			if res['context'].get('report_action'):
				report_lines = res['context']['report_action']['data']['report_lines']
			else:
				report_lines = res.get('data').get('report_lines')

			return self._print_excel(report_lines,report_name='balance_sheet')
		else:
			return res

	def _print_general_ledger_excel_report(self,report_lines):
		filename = 'General Ledger.xls'
		workbook = xlwt.Workbook()
		worksheet = workbook.add_sheet('Sheet 1')
		date_format = xlwt.XFStyle()
		date_format.num_format_str = 'dd/mm/yyyy'
		style_header = xlwt.easyxf(
			"font:height 300; font: name Liberation Sans, bold on,color black; align: horiz center")
		style_line = xlwt.easyxf(
			"font:bold on,color black;")
		worksheet.row(0).height_mismatch = True
		worksheet.row(0).height = 500
		worksheet.write_merge(0, 0, 0, 5, self.env.company.name + " : General Ledger Report", style=style_header)
		worksheet.write(2, 0, 'Journals')
		worksheet.write(2, 1, 'Display Account')
		worksheet.write(2, 2, 'Target Moves')
		worksheet.write(2, 3, 'Sorted By')
		if self.date_from:
			worksheet.write(2, 4, 'Date From')
		if self.date_to:
			worksheet.write(2, 5, 'Date To')
		journals = ', '.join([ lt.code or '' for lt in self.journal_ids ])
		if self.display_account == 'all':
			display_account = 'All accounts'
		elif self.display_account == 'movement':
			display_account = 'With movements'
		else:
			display_account = 'With balance not equal to zero'
		worksheet.write(3, 0, journals)
		worksheet.write(3, 1, display_account )
		worksheet.write(3, 2, 'All Posted Entries' if self.target_move == 'posted' else 'All Entries')
		worksheet.write(3, 3, 'Date' if self.sortby == 'sort_date' else 'Journal and Partner')
		if self.date_from:
			worksheet.write(3, 4, self.date_from, date_format)
		if self.date_to:
			worksheet.write(3, 5, self.date_to, date_format)

		worksheet.write(5, 0, 'Date')
		worksheet.write(5, 1, 'JRNL')
		worksheet.write(5, 2, 'Partner')
		worksheet.write(5, 3, 'Ref')
		worksheet.write(5, 4, 'Move')
		worksheet.write(5, 5, 'Entry Label')
		worksheet.write(5, 6, 'Debit')
		worksheet.write(5, 7, 'Credit')
		worksheet.write(5, 8, 'Balance')
		row = 6
		col = 0

		for line in report_lines:
			flag = False
			worksheet.write_merge(row,row, 0,5, line.get('code') + line.get('name'),style=style_line )
			worksheet.write(row, col+6, line.get('debit'),style=style_line)
			worksheet.write(row, col+7, line.get('credit'),style=style_line)
			worksheet.write(row, col+8, line.get('balance'),style=style_line)
			for move_line in line.get('move_lines'):
				row+=1
				worksheet.write(row, col, move_line.get('ldate'),date_format)
				worksheet.write(row, col + 1, move_line.get('lcode'))
				worksheet.write(row, col + 2, move_line.get('partner_name'))
				worksheet.write(row, col + 3, move_line.get('lref'))
				worksheet.write(row, col + 4, move_line.get('move_name'))
				worksheet.write(row, col + 5, move_line.get('lname'))
				worksheet.write(row, col + 6, move_line.get('debit'))
				worksheet.write(row, col + 7, move_line.get('credit'))
				worksheet.write(row, col + 8, move_line.get('balance'))
				row+=1
				flag = True
			if not flag:
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

	def print_general_ledger(self):
		res = super(AccountingReportBi, self).print_general_ledger()
		if self._context.get('report_type') == 'excel':
			if res['context'].get('report_action'):
				report_lines = res['context']['report_action']['data']['Account']
			else:
				report_lines = res.get('data').get('Account')

			return self._print_excel(report_lines,report_name='general_ledger')
		else:
			return res

	def _print_trial_balance_excel_report(self,report_lines):
		filename = 'Trial Balance.xls'
		workbook = xlwt.Workbook()
		worksheet = workbook.add_sheet('Sheet 1')
		date_format = xlwt.XFStyle()
		date_format.num_format_str = 'dd/mm/yyyy'
		style_header = xlwt.easyxf(
			"font:height 300; font: name Liberation Sans, bold on,color black; align: horiz center")
		style_line = xlwt.easyxf(
			"font:bold on,color black;")
		worksheet.row(0).height_mismatch = True
		worksheet.row(0).height = 500
		worksheet.write_merge(0, 0, 0, 5, self.env.company.name + " : Trial Balance Report", style=style_header)
		worksheet.write(2,0,'Display Account')
		worksheet.write(2,1,'Target Moves')
		if self.date_from:
			worksheet.write(2, 2, 'Date From')
		if self.date_to:
			worksheet.write(2, 3, 'Date To')
		if self.display_account == 'all':
			display_account = 'All accounts'
		elif self.display_account == 'movement':
			display_account = 'With movements'
		else:
			display_account = 'With balance not equal to zero'
		worksheet.write(3,0,display_account)
		worksheet.write(3,1,'All Posted Entries' if self.target_move == 'posted' else 'All Entries')
		if self.date_from:
			worksheet.write(3, 2, self.date_from,date_format)
		if self.date_to:
			worksheet.write(3, 3, self.date_to,date_format)

		worksheet.write(4,0,'code')
		worksheet.write(4,1,'Account')
		worksheet.write(4,2,'Debit')
		worksheet.write(4,3,'Credit')
		worksheet.write(4,4,'Balance')
		row = 5
		col = 0
		for lines in report_lines:
			worksheet.write(row,col,lines.get('code'))
			worksheet.write(row,col+1,lines.get('name'))
			worksheet.write(row,col+2,lines.get('debit'))
			worksheet.write(row,col+3,lines.get('credit'))
			worksheet.write(row,col+4,lines.get('balance'))
			row+=1
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

	def print_trial_balance(self):
		res = super(AccountingReportBi, self).print_trial_balance()
		if self._context.get('report_type') == 'excel':
			if res['context'].get('report_action'):
				report_lines = res['context']['report_action']['data']['account_res']
			else:
				report_lines = res.get('data').get('account_res')

			return self._print_excel(report_lines, report_name='trial_balance')
		else:
			return res
