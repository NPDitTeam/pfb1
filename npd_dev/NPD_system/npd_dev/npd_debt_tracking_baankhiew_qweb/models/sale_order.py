# -*- coding: utf-8 -*-
from odoo import api, fields, models
from bahttext import bahttext


class NpdDebtTrackingBaankhiew(models.Model):
    _inherit = "npd.debt.tracking.baankhiew"

    def get_total_baht_text_sheet(self):
        """แปลงยอดเงินรวมเป็นตัวอักษรภาษาไทย"""
        return bahttext(self.amount_residual)

    def get_damage_baht_text_sheet(self):
        """แปลงยอดค่าปรับชำรุดเป็นตัวอักษรภาษาไทย"""
        return bahttext(self.amount_damage_residual)

    def get_amount_residual_formatted(self):
        """รูปแบบยอดเงินค้างชำระ"""
        return '{:,.2f}'.format(self.amount_residual)

    def get_amount_damage_formatted(self):
        """รูปแบบยอดค่าปรับชำรุด"""
        return '{:,.2f}'.format(self.amount_damage_residual)

    def get_lost_baht_text_sheet(self):
        """แปลงยอดค่าปรับหายเป็นตัวอักษรภาษาไทย"""
        return bahttext(self.amount_lost_residual)

    def get_amount_lost_formatted(self):
        """รูปแบบยอดค่าปรับหาย"""
        return '{:,.2f}'.format(self.amount_lost_residual)


    def get_total_baht_text_sheet_tax(self):
        """แปลงยอดค่า Tax เป็นตัวอักษรภาษาไทย"""
        return bahttext(self.amount_tax_residual)

    def get_amount_tax_formatted(self):
        """รูปแบบยอดค่า Tax"""
        return '{:,.2f}'.format(self.amount_tax_residual)
