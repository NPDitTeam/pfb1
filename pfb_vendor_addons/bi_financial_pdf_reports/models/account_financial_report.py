# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
import time
from odoo.exceptions import UserError


class AccountFinancialReport(models.Model):
	_name = 'account.financial.report'

	def _get_children_by_order(self):
		res = self
		children = self.search([('parent_id', 'in', self.ids)], order='sequence ASC')
		if children:
			for child in children:
				res += child._get_children_by_order()
		return res

	@api.depends('parent_id', 'parent_id.level')
	def _get_level(self):
		for report in self:
			level = 0
			if report.parent_id:
				level = report.parent_id.level + 1
			report.level = level

	name = fields.Char('Report Name', required=True, translate=True)
	level = fields.Integer(compute='_get_level', string='Level', store=True)
	sequence = fields.Integer('Sequence')
	parent_id = fields.Many2one('account.financial.report', 'Parent')
	children_ids = fields.One2many('account.financial.report', 'parent_id', 'Account Report')
	type = fields.Selection([
		('sum', 'View'),
		('accounts', 'Accounts'),
		('account_type', 'Account Type'),
		('account_report', 'Report Value'),
	], 'Type', default='sum')
	account_ids = fields.Many2many('account.account', 'account_account_financial_report', 'report_line_id',
								   'account_id', 'Accounts')
	account_report_id = fields.Many2one('account.financial.report', 'Report Value')
	account_type_ids = fields.Many2many('account.account.type', 'account_account_financial_report_type', 'report_id',
										'account_type_id', 'Account Types')
	sign = fields.Selection([('-1', 'Reverse balance sign'), ('1', 'Preserve balance sign')], 'Sign on Reports',
							required=True, default='1',
							help='For accounts that are typically more debited than credited and that you would like to print as negative amounts in your reports, you should reverse the sign of the balance; e.g.: Expense account. The same applies for accounts that are typically more credited than debited and that you would like to print as positive amounts in your reports; e.g.: Income account.')
	display_detail = fields.Selection([
		('no_detail', 'No detail'),
		('detail_flat', 'Display children flat'),
		('detail_with_hierarchy', 'Display children with hierarchy')
	], 'Display details', default='detail_flat')
	style_overwrite = fields.Selection([
		('0', 'Automatic formatting'),
		('1', 'Main Title 1 (bold, underlined)'),
		('2', 'Title 2 (bold)'),
		('3', 'Title 3 (bold, smaller)'),
		('4', 'Normal Text'),
		('5', 'Italic Text (smaller)'),
		('6', 'Smallest Text'),
	], 'Financial Report Style', default='0',
		help="You can set up here the format you want this record to be displayed. If you leave the automatic formatting, it will be computed based on the financial reports hierarchy (auto-computed field 'level').")


class AccountingReportBi(models.TransientModel):
	_name = "accounting.report.bi"
	_description = "Accounting Report"

	@api.model
	def _get_account_report(self):
		reports = []
		if self._context.get('active_id'):
			menu = self.env['ir.ui.menu'].browse(self._context.get('active_id')).name
			reports = self.env['account.financial.report'].search([('name', 'ilike', menu)])
		return reports and reports[0] or False

	company_id = fields.Many2one('res.company', string='Company', readonly=True,
								 default=lambda self: self.env.user.company_id)
	journal_ids = fields.Many2many('account.journal', string='Journals', required=True,
								   default=lambda self: self.env['account.journal'].search([]))
	date_from = fields.Date(string='Start Date')
	date_to = fields.Date(string='End Date')
	display_account = fields.Selection([('all', 'All'), ('movement', 'With movements'),
										('not_zero', 'With balance is not equal to 0'), ],
									   string='Display Accounts', required=True, default='movement')
	target_move = fields.Selection([('posted', 'All Posted Entries'),
									('all', 'All Entries'),
									], string='Target Moves', required=True, default='posted')
	enable_filter = fields.Boolean(string='Enable Comparison')
	account_report_id = fields.Many2one('account.financial.report', string='Account Reports',
										default=_get_account_report)
	label_filter = fields.Char(string='Column Label',
							   help="This label will be displayed on report to show the balance computed for the given comparison filter.")
	filter_cmp = fields.Selection([('filter_no', 'No Filters'), ('filter_date', 'Date')], string='Filter by',
								  required=True, default='filter_no')
	date_from_cmp = fields.Date(string='Start Date')
	date_to_cmp = fields.Date(string='End Date')
	debit_credit = fields.Boolean(string='Display Debit/Credit Columns',
								  help="This option allows you to get more details about the way your balances are computed. Because it is space consuming, we do not allow to use it while doing a comparison.")
	initial_balance = fields.Boolean(string='Include Initial Balances',
									 help='If you selected date, this field allow you to add a row to display the amount of debit/credit/balance that precedes the filter you\'ve set.')
	sortby = fields.Selection([('sort_date', 'Date'), ('sort_journal_partner', 'Journal & Partner')], string='Sort by',
							  required=True, default='sort_date')

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
			tables, where_clause, where_params = self.env['account.move.line']._query_get()
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

	def _compute_report_balance(self, reports):
		res = {}
		fields = ['credit', 'debit', 'balance']
		for report in reports:
			if report.id in res:
				continue
			res[report.id] = dict((fn, 0.0) for fn in fields)
			if report.type == 'accounts':
				res[report.id]['account'] = self._compute_account_balance(report.account_ids)
				for value in res[report.id]['account'].values():
					for field in fields:
						res[report.id][field] += value.get(field)
			elif report.type == 'account_type':
				accounts = self.env['account.account'].search([('user_type_id', 'in', report.account_type_ids.ids)])
				res[report.id]['account'] = self._compute_account_balance(accounts)
				for value in res[report.id]['account'].values():
					for field in fields:
						res[report.id][field] += value.get(field)
			elif report.type == 'account_report' and report.account_report_id:
				res2 = self._compute_report_balance(report.account_report_id)
				for key, value in res2.items():
					for field in fields:
						res[report.id][field] += value[field]
			elif report.type == 'sum':
				res2 = self._compute_report_balance(report.children_ids)
				for key, value in res2.items():
					for field in fields:
						res[report.id][field] += value[field]
		return res

	def get_account_lines(self):
		lines = []
		account_report = self.env['account.financial.report'].search([('id', '=', self.account_report_id.id)])
		child_reports = account_report._get_children_by_order()
		used_context_dict = {
			'state': self.target_move,
			'date_from': self.date_from,
			'date_to': self.date_to,
			'journal_ids': [a.id for a in self.journal_ids],
			'strict_range': True
		}
		res = self.with_context(used_context_dict)._compute_report_balance(child_reports)
		if self.enable_filter:
			comparison_context_dict = {
				'journal_ids': [a.id for a in self.journal_ids],
				'state': self.target_move,
			}
			if self.filter_cmp == 'filter_date':
				comparison_context_dict.update({"date_to": self.date_to_cmp,
												"date_from": self.date_from_cmp})
			comparison_res = self.with_context(comparison_context_dict)._compute_report_balance(child_reports)
			for report_id, value in comparison_res.items():
				res[report_id]['comp_bal'] = value['balance']
				report_acc = res[report_id].get('account')
				if report_acc:
					for account_id, val in comparison_res[report_id].get('account').items():
						report_acc[account_id]['comp_bal'] = val['balance']

		for report in child_reports:
			vals = {
				'name': report.name,
				'balance': res[report.id]['balance'] * int(report.sign),
				'type': 'report',
				'level': bool(report.style_overwrite) and int(report.style_overwrite) or report.level,
				'account_type': report.type or False,  # used to underline the financial report balances
			}
			if self.debit_credit:
				vals['debit'] = res[report.id]['debit']
				vals['credit'] = res[report.id]['credit']

			if self.enable_filter:
				vals['balance_cmp'] = res[report.id]['comp_bal'] * int(report.sign)

			lines.append(vals)
			if report.display_detail == 'no_detail':
				continue

			if res[report.id].get('account'):
				sub_lines = []
				for account_id, value in res[report.id]['account'].items():
					flag = False
					account = self.env['account.account'].browse(account_id)
					vals = {
						'name': account.code + ' ' + account.name,
						'balance': value['balance'] * int(report.sign) or 0.0,
						'type': 'account',
						'level': report.display_detail == 'detail_with_hierarchy' and 4,
						'account_type': account.internal_type,
					}
					if self.debit_credit:
						vals['debit'] = value['debit']
						vals['credit'] = value['credit']
						if not account.company_id.currency_id.is_zero(
								vals['debit']) or not account.company_id.currency_id.is_zero(vals['credit']):
							flag = True
					if not account.company_id.currency_id.is_zero(vals['balance']):
						flag = True
					if self.enable_filter:
						vals['balance_cmp'] = value['comp_bal'] * int(report.sign)
						if not account.company_id.currency_id.is_zero(vals['balance_cmp']):
							flag = True
					if flag:
						sub_lines.append(vals)
				lines += sorted(sub_lines, key=lambda sub_line: sub_line['name'])
		return lines

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
		final_dict.update({'report_lines': report_lines,
						   'name': self.account_report_id.name,
						   'debit_credit': self.debit_credit,
						   'enable_filter': self.enable_filter,
						   'label_filter': self.label_filter,
						   'target_move': self.target_move,
						   'date_from': self.date_from,
						   'date_to': self.date_to
						   })
		return self.env.ref('bi_financial_pdf_reports.action_report_balancesheet').report_action(self, data=final_dict)

	
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
		final_dict.update({'report_lines': report_lines,
						   'name': self.account_report_id.name,
						   'debit_credit': self.debit_credit,
						   'enable_filter': self.enable_filter,
						   'label_filter': self.label_filter,
						   'target_move': self.target_move,
						   'date_from': self.date_from,
						   'date_to': self.date_to
						   })
		return self.env.ref('bi_financial_pdf_reports.action_report_profit_loss').report_action(self, data=final_dict)	

	
	def _get_accounts(self, accounts, display_account):
		account_result = {}
		tables, where_clause, where_params = self.env['account.move.line']._query_get()
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
		final_dict.update({'account_res': account_res,
						   'display_account': self.display_account,
						   'target_move': self.target_move,
						   'date_from': self.date_from,
						   'date_to': self.date_to,

						   })
		return self.env.ref('bi_financial_pdf_reports.action_report_trial_balance').report_action(self, data=final_dict)

	def _get_account_move_entry(self, accounts, init_balance, sortby, display_account):
		"""
		:param:
				accounts: the recordset of accounts
				init_balance: boolean value of initial_balance
				sortby: sorting by date or partner and journal
				display_account: type of account(receivable, payable and both)

		Returns a dictionary of accounts with following key and value {
				'code': account code,
				'name': account name,
				'debit': sum of total debit amount,
				'credit': sum of total credit amount,
				'balance': total balance,
				'amount_currency': sum of amount_currency,
				'move_lines': list of move line
		}
		"""
		cr = self.env.cr
		MoveLine = self.env['account.move.line']
		move_lines = {x: [] for x in accounts.ids}

		# Prepare initial sql query and Get the initial move lines
		if init_balance:
			init_tables, init_where_clause, init_where_params = MoveLine.with_context(date_from=self.env.context.get('date_from'), date_to=False, initial_bal=True)._query_get()
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
		tables, where_clause, where_params = MoveLine._query_get()
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
				'display_account': display_account,
				'target_move': self.target_move,
				'sortby': sortby,
				'date_from': self.date_from,
				'date_to': self.date_to
			}
		)
		return self.env.ref('bi_financial_pdf_reports.action_report_general_ledger').report_action(self,
																								   data=final_dict)
