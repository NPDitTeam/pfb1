# -*- coding: utf-8 -*-
import calendar
import datetime

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError




class WithholdingTaxCert(models.Model):
    _inherit = "withholding.tax.cert"

    report_late_mo = fields.Selection(
        [
            ("0", "0 month"),
            ("1", "1 month"),
            ("2", "2 months"),
            ("3", "3 months"),
            ("4", "4 months"),
            ("5", "5 months"),
            ("6", "6 months"),
        ],
        string="Report Late",
        default="0",
        required=True,
    )
    report_date = fields.Date(
        string="Report Date",
        compute="_compute_report_date",
        store=True,
    )

    @api.depends("report_late_mo", "date")
    def _compute_report_date(self):
        for rec in self:
            if rec.date:
                eval_date = rec.date + relativedelta(
                    months=int(rec.report_late_mo)
                )
                last_date = calendar.monthrange(eval_date.year, eval_date.month)[1]
                rec.report_date = datetime.date(
                    eval_date.year, eval_date.month, last_date
                )
            else:
                rec.report_date = False

    @api.depends("wt_line")
    def _compute_amount(self):
        for wht in self:
            wht.base_amount = sum(line.base for line in wht.wt_line)
            wht.tax_amount = sum(line.amount for line in wht.wt_line)
        
    @api.depends('income_tax_form')
    def _get_account_id(self):
        for wht in self:
            if wht.income_tax_form == 'pnd1':
                wht.account_id = wht.company_id.account_pnd1_withholding_tax_id.id or None
            elif wht.income_tax_form == 'pnd1a':
                wht.account_id = wht.company_id.account_pnd1a_withholding_tax_id.id or None
            elif wht.income_tax_form == 'pnd3':
                wht.account_id = wht.company_id.account_pnd3_withholding_tax_id.id or None
            elif wht.income_tax_form == 'pnd3a':
                wht.account_id = wht.company_id.account_pnd3a_withholding_tax_id.id or None
            elif wht.income_tax_form == 'pnd53':
                wht.account_id = wht.company_id.account_pnd53_withholding_tax_id.id or None

    
    # @api.depends('income_tax_form')
    # def _get_percent_tax(self):
    #     for wht in self:
    #         if wht.income_tax_form == 'pnd1':
    #             wht.percent_tax = self.env.company.percent_pnd1 
    #         elif wht.income_tax_form == 'pnd3':
    #             wht.percent_tax = self.env.company.percent_pnd3 
    #         elif wht.income_tax_form == 'pnd3a':
    #             wht.percent_tax = self.env.company.percent_pnd3a
    #         elif wht.income_tax_form == 'pnd53':
    #             wht.percent_tax = self.env.company.percent_pnd53
    #         else:
    #             wht.percent_tax = 0
        
    base_amount = fields.Float(string='Base Amount',compute='_compute_amount')
    tax_amount = fields.Float(string='Tax Amount',compute='_compute_amount')
    account_id = fields.Many2one('account.account', string='Account', compute='_get_account_id', store=True,)
    # percent_tax = fields.Integer('percent_tax', compute='_get_percent_tax')


    @api.depends("payment_id", "move_id","state")
    def _compute_wt_cert_data(self):
        super(WithholdingTaxCert, self)._compute_wt_cert_data()
        for rec in self:
            if rec.name is False and rec.state == 'done':
                seq_ids = self.env["ir.sequence"].search([('code', '=', "withholding.tax"),
                                    ('company_id', '=', rec.company_id.id)],order='company_id')
                if seq_ids:
                    rec.name = seq_ids[0].next_by_id(sequence_date=rec.date)
                else:
                    rec.name = self.env["ir.sequence"].next_by_code("withholding.tax")

    @api.onchange('supplier_partner_id')
    def _onchange_supplier_partner_id(self):
        for wht in self:
            if wht.supplier_partner_id.company_type == 'company':
                wht.income_tax_form = 'pnd53'
            elif wht.supplier_partner_id.company_type == 'person':
                wht.income_tax_form = 'pnd3'
            else:
                wht.income_tax_form = None

class WithholdingTaxCertLine(models.Model):
    _inherit = "withholding.tax.cert.line"

    @api.onchange("wt_percent","base")
    def _onchange_wt_percent(self):
        if self.wt_percent and self.base:
            self.amount = self.base * self.wt_percent / 100
        else:
            self.amount = 0.0
