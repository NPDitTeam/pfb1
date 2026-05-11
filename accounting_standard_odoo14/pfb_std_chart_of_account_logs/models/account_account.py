# Copyright 2009-2018 Noviat
# Copyright 2019 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import calendar
import logging
from odoo import _, api, fields, models
from datetime import datetime
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)


class Account(models.Model):
    _name = "account.account"
    _inherit = ['account.account','mail.thread', 'mail.activity.mixin']

    def get_cashflow_domain(self):
        cash_flow_id = self.env.ref('account_dynamic_reports.ins_account_financial_report_cash_flow0')
        if cash_flow_id:
            return [('parent_id.id', '=', cash_flow_id.id)]


    code = fields.Char(size=64, required=True, index=True,tracking=True)
    name = fields.Char(string="Account Name", required=True, index=True,tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
                                 default=lambda self: self.env.company,tracking=True)
    currency_id = fields.Many2one('res.currency', string='Account Currency',tracking=True,
                                  help="Forces all moves for this account to have this account currency.")
    user_type_id = fields.Many2one('account.account.type', string='Type', required=True,tracking=True,
                                   help="Account Type is used for information purpose, to generate country-specific legal reports, and set the rules to close a fiscal year and generate opening entries.")
    cash_flow_category = fields.Many2one('ins.account.financial.report', string="Cash Flow type", domain=get_cashflow_domain)
    wt_account = fields.Boolean(
        string="WT Account",
        tracking=True,
        default=False,
        help="If check, this account is for withholding tax",
    )
    tag_ids = fields.Many2many('account.account.tag', 'account_account_account_tag', string='Tags',tracking=True,
                               help="Optional tags you may want to assign for custom reporting")
    group_id = fields.Many2one('account.group', compute='_compute_account_group', tracking=True,store=True, readonly=True)
    root_id = fields.Many2one('account.root', compute='_compute_account_root',tracking=True, store=True)
    deprecated = fields.Boolean(index=True, tracking=True,default=False)
    allowed_journal_ids = fields.Many2many('account.journal',tracking=True, string="Allowed Journals",
                                           help="Define in which journals this account can be used. If empty, can be used in all journals.")
    tax_ids = fields.Many2many('account.tax', 'account_account_tax_default_rel',
                               'account_id', 'tax_id', string='Default Taxes',
                               check_company=True,tracking=True,
                               context={'append_type_to_tax_name': True})
    note = fields.Text('Internal Notes',tracking=True)