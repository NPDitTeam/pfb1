# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import base64
import io
import time

import xlwt
from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountingReportBi(models.TransientModel):
	_inherit = 'accounting.report.bi'

	branch_ids = fields.Many2many('res.branch', string="Branch")

	def _compute_account_balance(self, accounts):
		""" compute the balance, debit and credit for the provided accounts
		"""
		mapping = {
			'balance': "COALESCE(SUM(debit),0) - COALESCE(SUM(credit), 0) as balance",
			'debit': "COALESCE(SUM(debit), 0) as debit",
			'credit': "COALESCE(SUM(credit), 0) as credit",
		}

		res = {}
		for account in accounts:
			res[account.id] = dict.fromkeys(mapping, 0.0)
		if accounts:
			if self.branch_ids:
				domain = [('branch_id', 'in', [a.id for a in self.branch_ids])]
			else:
				domain = []
			tables, where_clause, where_params = self.env['account.move.line']._query_get(domain)
			tables = tables.replace('"', '') if tables else "account_move_line"
			wheres = [""]
			if where_clause.strip():
				wheres.append(where_clause.strip())
			filters = " AND ".join(wheres)

			request = "SELECT account_id as id, " + ', '.join(mapping.values()) + \
					  " FROM " + tables + \
					  " WHERE account_id IN %s " \
					  + filters + \
					  " GROUP BY account_id"
			params = (tuple(accounts._ids),) + tuple(where_params)
			self.env.cr.execute(request, params)
			for row in self.env.cr.dictfetchall():
				res[row['id']] = row
		return res

	def _print_balance_sheet_excel_report(self, report_lines):
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
		worksheet.write(2, 0, 'Target Move')
		if self.date_from:
			worksheet.write(2, 2, 'Start Date')
		if self.date_to:
			worksheet.write(2, 3, 'End Date')
		if self.branch_ids:
			print_branch = [a.name for a in self.branch_ids]
			worksheet.write(2, 1, 'Branch')
		worksheet.write(3, 0, 'All Posted Entries' if self.target_move == 'posted' else 'All Entries')
		if self.date_from:
			worksheet.write(3, 2, self.date_from, date_format)
		if self.date_to:
			worksheet.write(3, 3, self.date_to, date_format)
		if self.branch_ids:
			worksheet.write(3, 1, ', '.join([lt or '' for lt in print_branch]))
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
					worksheet.write(row, col, lines.get('name'), style_line)
					worksheet.write(row, col + 1, lines.get('debit'), style_line)
					worksheet.write(row, col + 2, lines.get('credit'), style_line)
					worksheet.write(row, col + 3, lines.get('balance'), style_line)
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

	def _print_general_ledger_excel_report(self, report_lines):
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
		worksheet.write_merge(0, 0, 0, 5,
							  self.env['res.users'].browse(self.env.uid).company_id.name + " : General Ledger Report",
							  style=style_header)
		worksheet.write(2, 0, 'Journals')
		worksheet.write(2, 1, 'Display Account')
		worksheet.write(2, 2, 'Target Moves')
		worksheet.write(2, 3, 'Sorted By')
		if self.branch_ids:
			worksheet.write(2, 4, 'Branch')
		if self.date_from:
			worksheet.write(2, 5, 'Date From')
		if self.date_to:
			worksheet.write(2, 6, 'Date To')
		journals = ', '.join([lt.code or '' for lt in self.journal_ids])
		if self.display_account == 'all':
			display_account = 'All accounts'
		elif self.display_account == 'movement':
			display_account = 'With movements'
		else:
			display_account = 'With balance not equal to zero'
		worksheet.write(3, 0, journals)
		worksheet.write(3, 1, display_account)
		worksheet.write(3, 2, 'All Posted Entries' if self.target_move == 'posted' else 'All Entries')
		worksheet.write(3, 3, 'Date' if self.sortby == 'sort_date' else 'Journal and Partner')
		if self.branch_ids:
			print_branch = [a.name for a in self.branch_ids]
			worksheet.write(3, 4, ', '.join([lt or '' for lt in print_branch]))
		if self.date_from:
			worksheet.write(3, 5, self.date_from, date_format)
		if self.date_to:
			worksheet.write(3, 6, self.date_to, date_format)

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
			worksheet.write_merge(row, row, 0, 5, line.get('code') + line.get('name'), style=style_line)
			worksheet.write(row, col + 6, line.get('debit'), style=style_line)
			worksheet.write(row, col + 7, line.get('credit'), style=style_line)
			worksheet.write(row, col + 8, line.get('balance'), style=style_line)
			for move_line in line.get('move_lines'):
				row += 1
				worksheet.write(row, col, move_line.get('ldate'), date_format)
				worksheet.write(row, col + 1, move_line.get('lcode'))
				worksheet.write(row, col + 2, move_line.get('partner_name'))
				worksheet.write(row, col + 3, move_line.get('lref'))
				worksheet.write(row, col + 4, move_line.get('move_name'))
				worksheet.write(row, col + 5, move_line.get('lname'))
				worksheet.write(row, col + 6, move_line.get('debit'))
				worksheet.write(row, col + 7, move_line.get('credit'))
				worksheet.write(row, col + 8, move_line.get('balance'))
				row += 1
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

	def _print_trial_balance_excel_report(self, report_lines):
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
		worksheet.write_merge(0, 0, 0, 5,
							  self.env['res.users'].browse(self.env.uid).company_id.name + " : Trial Balance Report",
							  style=style_header)
		worksheet.write(2, 0, 'Display Account')
		worksheet.write(2, 1, 'Target Moves')
		if self.branch_ids:
			worksheet.write(2, 2, 'Branch')
		if self.date_from:
			worksheet.write(2, 3, 'Date From')
		if self.date_to:
			worksheet.write(2, 4, 'Date To')
		if self.display_account == 'all':
			display_account = 'All accounts'
		elif self.display_account == 'movement':
			display_account = 'With movements'
		else:
			display_account = 'With balance not equal to zero'
		worksheet.write(3, 0, display_account)
		worksheet.write(3, 1, 'All Posted Entries' if self.target_move == 'posted' else 'All Entries')
		if self.date_from:
			worksheet.write(3, 3, self.date_from, date_format)
		if self.date_to:
			worksheet.write(3, 4, self.date_to, date_format)
		if self.branch_ids:
			print_branch = [a.name for a in self.branch_ids]
			worksheet.write(3, 2, ', '.join([lt or '' for lt in print_branch]))

		worksheet.write(4, 0, 'code')
		worksheet.write(4, 1, 'Account')
		worksheet.write(4, 2, 'Debit')
		worksheet.write(4, 3, 'Credit')
		worksheet.write(4, 4, 'Balance')
		row = 5
		col = 0
		for lines in report_lines:
			worksheet.write(row, col, lines.get('code'))
			worksheet.write(row, col + 1, lines.get('name'))
			worksheet.write(row, col + 2, lines.get('debit'))
			worksheet.write(row, col + 3, lines.get('credit'))
			worksheet.write(row, col + 4, lines.get('balance'))
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

		if not self.account_report_id:
			raise UserError('Misconfiguration. Please Update module.\n There is no any associated report.')
		final_dict = {}
		if self.date_to and self.date_from:
			if self.date_to <= self.date_from:
				raise UserError('End date should be greater then to start date.')
		if self.enable_filter and self.filter_cmp == 'filter_date':
			if self.date_to_cmp <= self.date_from_cmp:
				raise UserError('Comparison end date should be greater then to Comparison start date.')
		report_lines = self.get_account_lines()
		branch_name = [branch.name for branch in self.branch_ids]
		final_dict.update({'report_lines': report_lines,
						   'name': self.account_report_id.name,
						   'debit_credit': self.debit_credit,
						   'enable_filter': self.enable_filter,
						   'label_filter': self.label_filter,
						   'target_move': self.target_move,
						   'date_from': self.date_from,
						   'date_to': self.date_to,
						   'print_branch': branch_name
						   })
		if self._context.get('report_type') == 'excel':
			return self._print_excel(report_lines, report_name='balance_sheet')
		else:
			return self.env.ref('bi_financial_pdf_reports.action_report_balancesheet').report_action(self,
																									 data=final_dict)

	
	def check_report_profit(self):
		if not self.account_report_id:
			raise UserError('Misconfiguration. Please Update module.\n There is no any associated report.')
		final_dict = {}
		if self.date_to and self.date_from:
			if self.date_to <= self.date_from:
				raise UserError('End date should be greater then to start date.')
		if self.enable_filter and self.filter_cmp == 'filter_date':
			if self.date_to_cmp <= self.date_from_cmp:
				raise UserError('Comparison end date should be greater then to Comparison start date.')
		report_lines = self.get_account_lines()
		branch_name = [branch.name for branch in self.branch_ids]
		final_dict.update({'report_lines': report_lines,
						   'name': self.account_report_id.name,
						   'debit_credit': self.debit_credit,
						   'enable_filter': self.enable_filter,
						   'label_filter': self.label_filter,
						   'target_move': self.target_move,
						   'date_from': self.date_from,
						   'date_to': self.date_to,
						   'print_branch': branch_name
						   })
		if self._context.get('report_type') == 'excel':
			return self._print_excel(report_lines, report_name='balance_sheet')
		else:
			return self.env.ref('bi_financial_pdf_reports.action_report_profit_loss').report_action(self,
																									 data=final_dict)
		

	def _get_accounts(self, accounts, display_account):
		account_result = {}
		if self.branch_ids:
			domain = [('branch_id', 'in', [a.id for a in self.branch_ids])]
		else:
			domain = []
		tables, where_clause, where_params = self.env['account.move.line']._query_get(domain)
		tables = tables.replace('"', '')
		if not tables:
			tables = 'account_move_line'
		wheres = [""]
		if where_clause.strip():
			wheres.append(where_clause.strip())
		filters = " AND ".join(wheres)
		request = (
				"SELECT account_id AS id, SUM(debit) AS debit, SUM(credit) AS credit, (SUM(debit) - SUM(credit)) AS balance" + \
				" FROM " + tables + " WHERE account_id IN %s " + filters + " GROUP BY account_id")
		params = (tuple(accounts.ids),) + tuple(where_params)
		self.env.cr.execute(request, params)
		for row in self.env.cr.dictfetchall():
			account_result[row.pop('id')] = row

		account_res = []
		for account in accounts:
			res = dict((fn, 0.0) for fn in ['credit', 'debit', 'balance'])
			currency = account.currency_id and account.currency_id or account.company_id.currency_id
			res['code'] = account.code
			res['name'] = account.name
			if account.id in account_result:
				res['debit'] = account_result[account.id].get('debit')
				res['credit'] = account_result[account.id].get('credit')
				res['balance'] = account_result[account.id].get('balance')
			if display_account == 'all':
				account_res.append(res)
			if display_account == 'not_zero' and not currency.is_zero(res['balance']):
				account_res.append(res)
			if display_account == 'movement' and (
					not currency.is_zero(res['debit']) or not currency.is_zero(res['credit'])):
				account_res.append(res)
		return account_res

	def print_trial_balance(self):
		if self.date_to and self.date_from:
			if self.date_to <= self.date_from:
				raise UserError('End date should be greater then to start date.')
		display_account = self.display_account
		accounts = self.env['account.account'].search([])
		used_context_dict = {
			'state': self.target_move,
			'date_from': self.date_from,
			'date_to': self.date_to,
			'journal_ids': False,
			'strict_range': True
		}
		account_res = self.with_context(used_context_dict)._get_accounts(accounts, display_account)
		final_dict = {}
		branch_name = [branch.name for branch in self.branch_ids]
		final_dict.update({'account_res': account_res,
						   'display_account': self.display_account,
						   'target_move': self.target_move,
						   'date_from': self.date_from,
						   'date_to': self.date_to,
						   'print_branch': branch_name
						   })
		if self._context.get('report_type') == 'excel':
			return self._print_excel(account_res, report_name='trial_balance')
		else:
			return self.env.ref('bi_financial_pdf_reports.action_report_trial_balance').report_action(self,
																									  data=final_dict)

	def print_general_ledger(self):
		if self.date_to and self.date_from:
			if self.date_to <= self.date_from:
				raise UserError('End date should be greater then to start date.')
		init_balance = self.initial_balance
		sortby = self.sortby
		display_account = self.display_account
		codes = []
		if self.journal_ids:
			codes = [journal.code for journal in
					 self.env['account.journal'].search([('id', 'in', self.journal_ids.ids)])]
		branch_name = [branch.name for branch in self.branch_ids]
		used_context_dict = {
			'state': self.target_move,
			'date_from': self.date_from,
			'date_to': self.date_to,
			'journal_ids': [a.id for a in self.journal_ids],
			'strict_range': True
		}
		accounts = self.env['account.account'].search([])
		accounts_res = self.with_context(used_context_dict)._get_account_move_entry(accounts, init_balance, sortby,
																					display_account)
		final_dict = {}
		final_dict.update(
			{
				'time': time,
				'Account': accounts_res,
				'print_journal': codes,
				'print_branch': branch_name,
				'display_account': display_account,
				'target_move': self.target_move,
				'sortby': sortby,
				'date_from': self.date_from,
				'date_to': self.date_to
			}
		)
		if self._context.get('report_type') == 'excel':
			return self._print_excel(accounts_res, report_name='general_ledger')
		else:
			return self.env.ref('bi_financial_pdf_reports.action_report_general_ledger').report_action(self,
																									   data=final_dict)

	def _get_account_move_entry(self, accounts, init_balance, sortby, display_account):
		if self.branch_ids:
			domain = [('branch_id', 'in', [a.id for a in self.branch_ids])]
		else:
			domain = []
		cr = self.env.cr
		MoveLine = self.env['account.move.line']
		move_lines = {x: [] for x in accounts.ids}
		if init_balance:
			init_tables, init_where_clause, init_where_params = MoveLine._query_get(domain)
			init_wheres = [""]
			if init_where_clause.strip():
				init_wheres.append(init_where_clause.strip())
			init_filters = " AND ".join(init_wheres)
			filters = init_filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')
			sql = ("""SELECT 0 AS lid, l.account_id AS account_id, '' AS ldate, '' AS lcode, 0.0 AS amount_currency, '' AS lref, 'Initial Balance' AS lname, COALESCE(SUM(l.debit),0.0) AS debit, COALESCE(SUM(l.credit),0.0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) as balance, '' AS lpartner_id,\
				'' AS move_name, '' AS mmove_id, '' AS currency_code,\
				NULL AS currency_id,\
				'' AS invoice_id, '' AS invoice_type, '' AS invoice_number,\
				'' AS partner_name\
				FROM account_move_line l\
				LEFT JOIN account_move m ON (l.move_id=m.id)\
				LEFT JOIN res_currency c ON (l.currency_id=c.id)\
				LEFT JOIN res_partner p ON (l.partner_id=p.id)\
				JOIN account_journal j ON (l.journal_id=j.id)\
				WHERE l.account_id IN %s""" + filters + ' GROUP BY l.account_id')
			params = (tuple(accounts.ids),) + tuple(init_where_params)
			cr.execute(sql, params)
			for row in cr.dictfetchall():
				move_lines[row.pop('account_id')].append(row)

		sql_sort = 'l.date, l.move_id'
		if sortby == 'sort_journal_partner':
			sql_sort = 'j.code, p.name, l.move_id'

		# Prepare sql query base on selected parameters from wizard
		tables, where_clause, where_params = MoveLine._query_get(domain)
		wheres = [""]
		if where_clause.strip():
			wheres.append(where_clause.strip())
		filters = " AND ".join(wheres)
		filters = filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')

		# Get move lines base on sql query and Calculate the total balance of move lines
		sql = ('''SELECT l.id AS lid, l.account_id AS account_id, l.date AS ldate, j.code AS lcode, l.currency_id, l.amount_currency, l.ref AS lref, l.name AS lname, COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) AS balance,\
			m.name AS move_name, c.symbol AS currency_code, p.name AS partner_name\
			FROM account_move_line l\
			JOIN account_move m ON (l.move_id=m.id)\
			LEFT JOIN res_currency c ON (l.currency_id=c.id)\
			LEFT JOIN res_partner p ON (l.partner_id=p.id)\
			JOIN account_journal j ON (l.journal_id=j.id)\
			JOIN account_account acc ON (l.account_id = acc.id) \
			WHERE l.account_id IN %s ''' + filters + ''' GROUP BY l.id, l.account_id, l.date, j.code, l.currency_id, l.amount_currency, l.ref, l.name, m.name, c.symbol, p.name ORDER BY ''' + sql_sort)
		params = (tuple(accounts.ids),) + tuple(where_params)
		cr.execute(sql, params)

		for row in cr.dictfetchall():
			balance = 0
			for line in move_lines.get(row['account_id']):
				balance += line['debit'] - line['credit']
			row['balance'] += balance
			move_lines[row.pop('account_id')].append(row)

		# Calculate the debit, credit and balance for Accounts
		account_res = []
		for account in accounts:
			currency = account.currency_id and account.currency_id or account.company_id.currency_id
			res = dict((fn, 0.0) for fn in ['credit', 'debit', 'balance'])
			res['code'] = account.code
			res['name'] = account.name
			res['move_lines'] = move_lines[account.id]
			for line in res.get('move_lines'):
				res['debit'] += line['debit']
				res['credit'] += line['credit']
				res['balance'] = line['balance']
			if display_account == 'all':
				account_res.append(res)
			if display_account == 'movement' and res.get('move_lines'):
				account_res.append(res)
			if display_account == 'not_zero' and not currency.is_zero(res['balance']):
				account_res.append(res)

		return account_res
