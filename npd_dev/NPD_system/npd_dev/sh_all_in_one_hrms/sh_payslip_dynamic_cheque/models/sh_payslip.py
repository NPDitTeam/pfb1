# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api
import datetime


class ResBank(models.Model):
    _inherit = 'res.bank'

    logo = fields.Binary('Logo')


class ShPayslip(models.Model):
    _inherit = 'hr.payslip'

    sh_cheque_format_id = fields.Many2one(
        'sh.payslip.dynamic.cheque', "Cheque Format")
    sh_account_no = fields.Char('Account No')
    sh_bank_id = fields.Many2one('res.bank', 'Bank')
    sh_partner_title = fields.Char("Employee Title")
    sh_cheque_no = fields.Char("Cheque No")
    sh_free_text = fields.Char("Free Text One")
    sh_free_text_two = fields.Char("Free Text Two")
    sh_free_text_three = fields.Char("Free Text Three")
    sh_confirm_date = fields.Date("Confirmed Date", defult=fields.Date.today())

    def action_payslip_done(self):
        res = super(ShPayslip, self).action_payslip_done()
        self.sh_confirm_date = fields.Date.today()
        return res

    @api.model
    def get_net_amount(self):
        net_amount = 0.0
        if self and self.line_ids:
            line = self.line_ids.sudo().search([('code', '=', 'NET')], limit=1)
            if line:
                net_amount += line.total
        return net_amount

    @api.model
    def get_cheque_border(self):
        border_str = ''
        if self.sh_cheque_format_id and self.sh_cheque_format_id.sh_border_width and self.sh_cheque_format_id.sh_border_color:
            border_str += str('border:')+' '+str(self.sh_cheque_format_id.sh_border_width) + \
                'px'+' '+str('solid')+' ' + \
                str(self.sh_cheque_format_id.sh_border_color)+';'
        return border_str

    @api.model
    def get_date(self):
        date_string = ''
        if self.sh_cheque_format_id:
            if self.sh_cheque_format_id.sh_date_format and self.sh_confirm_date and self.sh_cheque_format_id.sh_year_format and not self.sh_cheque_format_id.sh_date_separator:
                payslip_date = self.sh_confirm_date
                date_string += datetime.datetime.strptime(
                    payslip_date, "%Y-%m-%d").strftime("%d%m%Y")
            elif self.sh_cheque_format_id.sh_date_format == 'dd_mm' and self.sh_confirm_date and self.sh_cheque_format_id.sh_year_format == 'yy' and self.sh_cheque_format_id.sh_date_separator:
                payslip_date = self.sh_confirm_date
                day = str(payslip_date.day)
                month = str(payslip_date.month)
                year = str(payslip_date.year)
                year_list = []
                for y in year:
                    year_list.append(y)
                complete_date_string = day+" " + \
                    month+" "+year_list[2]+year_list[3]
                date_string += str(complete_date_string).replace(" ",
                                                                 str(self.sh_cheque_format_id.sh_date_separator))
            elif self.sh_cheque_format_id.sh_date_format == 'dd_mm' and self.sh_confirm_date and self.sh_cheque_format_id.sh_year_format == 'yyyy' and self.sh_cheque_format_id.sh_date_separator:
                payslip_date = self.sh_confirm_date
                day = str(payslip_date.day)
                month = str(payslip_date.month)
                year = str(payslip_date.year)
                complete_date_string = day+" "+month+" "+year
                date_string += str(complete_date_string).replace(" ",
                                                                 str(self.sh_cheque_format_id.sh_date_separator))
            elif self.sh_cheque_format_id.sh_date_format == 'mm_dd' and self.sh_confirm_date and self.sh_cheque_format_id.sh_year_format == 'yy' and self.sh_cheque_format_id.sh_date_separator:
                payslip_date = self.sh_confirm_date
                day = str(payslip_date.day)
                month = str(payslip_date.month)
                year = str(payslip_date.year)
                year_list = []
                for y in year:
                    year_list.append(y)
                complete_date_string = month+" " + \
                    day+" "+year_list[2]+year_list[3]
                date_string += str(complete_date_string).replace(" ",
                                                                 str(self.sh_cheque_format_id.sh_date_separator))
            elif self.sh_cheque_format_id.sh_date_format == 'mm_dd' and self.sh_confirm_date and self.sh_cheque_format_id.sh_year_format == 'yyyy' and self.sh_cheque_format_id.sh_date_separator:
                payslip_date = self.sh_confirm_date
                day = str(payslip_date.day)
                month = str(payslip_date.month)
                year = str(payslip_date.year)
                complete_date_string = month+" "+day+" "+year
                date_string += str(complete_date_string).replace(" ",
                                                                 str(self.sh_cheque_format_id.sh_date_separator))
        return date_string

    @api.model
    def get_date_letter_spacing(self):
        letter_spacing = ''
        if self.sh_cheque_format_id:
            int_letter_spacing = int(
                self.sh_cheque_format_id.sh_date_letter_spacing)
            letter_spacing += str(int_letter_spacing)
        return letter_spacing

    @api.model
    def get_amount_in_words(self):
        str_amount_in_words = ''
        if self.sh_cheque_format_id:
            amount_in_words = self.company_id.currency_id.amount_to_text(
                self.get_net_amount())
            str_amount_in_words += str(amount_in_words)
        return str_amount_in_words
