# -*- coding: utf-8 -*-
import odoo
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ResCompany(models.Model):
    _inherit = "res.company"

    account_withholding_tax_id = fields.Many2one(
        comodel_name='account.account',
        string="Withholding Tax Account",
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    account_pnd1_withholding_tax_id = fields.Many2one(
        comodel_name='account.account',
        string="PND1 Withholding Tax",
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    account_pnd1a_withholding_tax_id = fields.Many2one(
        comodel_name='account.account',
        string="PND1a Withholding Tax",
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    account_pnd3_withholding_tax_id = fields.Many2one(
        comodel_name='account.account',
        string="PND3 Withholding Tax",
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    account_pnd3a_withholding_tax_id = fields.Many2one(
        comodel_name='account.account',
        string="PND3a Withholding Tax",
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    account_pnd53_withholding_tax_id = fields.Many2one(
        comodel_name='account.account',
        string="PND53 Withholding Tax",
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    # percent_pnd1 = fields.Integer(string='Percent Pnd1')
    # percent_pnd3 = fields.Integer(string='Percent Pnd3')
    # percent_pnd3a = fields.Integer(string='Percent Pnd3a')
    # percent_pnd53 = fields.Integer(string='Percent Pnd53')

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    account_withholding_tax_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.account_withholding_tax_id",
        string="PND1",
        readonly=False,
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )

    account_pnd1_withholding_tax_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.account_pnd1_withholding_tax_id",
        string="PND1",
        readonly=False,
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    account_pnd1a_withholding_tax_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.account_pnd1a_withholding_tax_id",
        string="PND1a",
        readonly=False,
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    account_pnd3_withholding_tax_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.account_pnd3_withholding_tax_id",
        string="PND3",
        readonly=False,
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    account_pnd3a_withholding_tax_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.account_pnd3a_withholding_tax_id",
        string="PND3a",
        readonly=False,
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    account_pnd53_withholding_tax_id = fields.Many2one(
        comodel_name="account.account",
        related="company_id.account_pnd53_withholding_tax_id",
        string="PND53",
        readonly=False,
        # domain=lambda self: "[('deprecated', '=', False), ('company_id', '=', id)]"
    )
    # percent_pnd1 = fields.Integer(string='Percent Pnd1', related="company_id.percent_pnd1",readonly=False)
    # percent_pnd3 = fields.Integer(string='Percent Pnd3', related="company_id.percent_pnd3",readonly=False)
    # percent_pnd3a = fields.Integer(string='Percent Pnd3a', related="company_id.percent_pnd3a",readonly=False)
    # percent_pnd53 = fields.Integer(string='Percent Pnd53', related="company_id.percent_pnd53",readonly=False)