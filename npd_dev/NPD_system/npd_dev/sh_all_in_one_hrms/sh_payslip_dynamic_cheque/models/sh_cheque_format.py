# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    group_enable_sh_payslip_dynamic_cheque = fields.Boolean(
        "Enable Payslip Dynamic Cheque", implied_group='sh_all_in_one_hrms.group_enable_sh_payslip_dynamic_cheque')


class ShChequeFormat(models.Model):
    _name = 'sh.payslip.dynamic.cheque'
    _description = "Dynamic Cheque"
    _rec_name = 'name'

    name = fields.Char("Cheque Name", required=True)
    sh_border_width = fields.Char("Border Width", default="1")
    sh_border_color = fields.Char(
        "Border Color", help="Choose your color")
    sh_font_size = fields.Char("Font Size")
    sh_color = fields.Char("Color", help="Choose your color")
    sh_print_partner = fields.Boolean("Print Partner")
    sh_partner_font_bold = fields.Boolean("Font Bold")
    sh_partner_title = fields.Selection(
        [('prefix', 'Prefix'), ('suffix', 'Suffix')], default='prefix', string="Partner Title")
    sh_partner_from_top = fields.Char("Partner Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_print_date = fields.Boolean("Print Date")
    sh_date_separator = fields.Char("Separator")
    sh_date_format = fields.Selection(
        [('dd_mm', 'DD MM'), ('mm_dd', 'MM DD')], default='dd_mm', string="Date Format")
    sh_year_format = fields.Selection(
        [('yy', 'YY'), ('yyyy', 'YYYY')], default='yy', string="Year Format")
    sh_date_from_top = fields.Char("Date Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_print_amount = fields.Boolean("Print Amount")
    sh_print_currency = fields.Boolean("Print Currency")
    sh_print_star = fields.Boolean("Print Star")
    sh_amount_from_top = fields.Char("Amount Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_print_amount_words = fields.Boolean("Print Amount Words")
    sh_amount_words_print_star = fields.Boolean("Print Star")
    sh_amount_words_font_bold = fields.Boolean("Font Bold")
    sh_amount_words_from_first_top = fields.Char(
        "Amount In Words Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_date_letter_spacing = fields.Float("Date Letter Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_print_company = fields.Boolean("Print Company")
    sh_print_company_from_top = fields.Char("Company Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_print_cheque_no = fields.Boolean("Print Cheque No")
    sh_print_acc_pay = fields.Boolean("Print A/C PAY")
    sh_print_acc_pay_from_top = fields.Char("A/C PAY Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_print_first_signature = fields.Boolean("Print Signature")
    sh_print_free_text_one = fields.Boolean("Print Free Text One")
    sh_print_free_text_one_from_top = fields.Char(
        "Free Text One Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_print_short_code = fields.Boolean("Print Short Code")
    sh_print_address = fields.Boolean("Print Bank Address")
    sh_print_acc_no = fields.Boolean("Print Account Number")
    sh_print_free_text_two = fields.Boolean("Print Free Text Two")
    sh_print_free_text_two_from_top = fields.Char(
        "Free Text Two Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_print_free_text_three = fields.Boolean("Print Free Text Three")
    sh_print_free_text_three_from_top = fields.Char(
        "Free Text Three Spacing", help="(1)=>padding: 25px 50px 75px 100px;==>top padding is 25px right padding is 50px bottom padding is 75px left padding is 100px,(2)=>padding: 25px 50px 75px;==>top padding is 25px right and left paddings are 50px bottom padding is 75px,(3)=>padding: 25px 50px;==>top and bottom paddings are 25px right and left paddings are 50px,(4)=>padding: 25px;==>all four paddings are 25px")
    sh_date_font_size = fields.Char("Font Size", default='10px')
    sh_date_font_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_amount_digit_font_size = fields.Char("Font Size", default='10px')
    sh_amount_digit_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_amount_word_font_size = fields.Char("Font Size", default='10px')
    sh_amount_word_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_company_font_size = fields.Char("Font Size", default='10px')
    sh_company_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_cheque_no_font_size = fields.Char("Font Size", default='10px')
    sh_cheque_no_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_short_code_font_size = fields.Char("Font Size", default='10px')
    sh_short_code_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_address_font_size = fields.Char("Font Size", default='10px')
    sh_address_font_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_acc_no_font_size = fields.Char("Font Size", default='10px')
    sh_acc_no_font_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_acc_pay_font_size = fields.Char("Font Size", default='10px')
    sh_acc_pay_font_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_free_text_one_font_size = fields.Char("Font Size", default='10px')
    sh_free_text_one_font_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_free_text_two_font_size = fields.Char("Font Size", default='10px')
    sh_free_text_two_font_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_free_text_three_font_size = fields.Char("Font Size", default='10px')
    sh_free_text_three_font_color = fields.Char(
        "Font Color", help="Choose your color")
    sh_print_stub = fields.Boolean("Print Salary Information")
