# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

from odoo import models, fields, api, _


class sale_order_line(models.Model):
    _inherit = "sale.order.line"

    uom_category_id = fields.Many2one('uom.category', related='product_uom.category_id', string='UOM Category')
    second_uom_id = fields.Many2one('uom.uom', string="Secondary UOM")
    second_uom_qty = fields.Float('Secondary Qty')
    second_price = fields.Float('Second Price')

    @api.onchange('second_price', 'product_uom', 'second_uom_id')
    def onchange_second_price_unit(self):
        if self.second_uom_id and self.product_uom and self.second_price:
            if self.second_uom_id.id == self.product_uom.id:
                self.price_unit = self.second_price
            else:
                if self.product_uom.uom_type == 'smaller':
                    self.price_unit = self.second_price / self.product_uom.factor
                elif self.product_uom.uom_type == 'bigger':
                    self.price_unit = self.second_price * self.product_uom.factor_inv
                else:
                    if self.second_uom_id.uom_type == 'smaller':
                        self.price_unit = self.second_price * self.second_uom_id.factor
                    elif self.second_uom_id.uom_type == 'bigger':
                        self.price_unit = self.second_price / self.second_uom_id.factor_inv
                    else:
                        self.price_unit = self.second_price

    @api.onchange('price_unit', 'product_uom', 'second_uom_id')
    def onchange_dev_price_unit(self):
        if self.second_uom_id and self.product_uom:
            if self.second_uom_id.id == self.product_uom.id:
                self.second_price = self.price_unit
            else:
                if self.second_uom_id.uom_type == 'smaller':
                    self.second_price = self.price_unit / self.second_uom_id.factor
                elif self.second_uom_id.uom_type == 'bigger':
                    self.second_price = self.price_unit * self.second_uom_id.factor_inv
                else:
                    if self.product_uom.uom_type == 'smaller':
                        self.second_price = self.price_unit * self.product_uom.factor
                    elif self.product_uom.uom_type == 'bigger':
                        self.second_price = self.price_unit / self.product_uom.factor_inv
                    else:
                        self.second_price = self.price_unit

    # def _prepare_invoice_line(self):
    #     res = super(sale_order_line, self)._prepare_invoice_line()
    #     print("res======", res)
    #     # ตรวจสอบว่า Database เป็น 'NPD_S_Group_New' หรือ 'NPD_Bangkok_New'
    #     current_db = self.env.cr.dbname
    #     # print("current_db", current_db)
    #     pfb_so_type = self.order_id.pfb_so_type
    #     # print("pfb_so_type",pfb_so_type)
    #     if current_db in ['test_2025_01', 'TEST_New', 'test', 'NPD_S_Group_New_V2', 'NPD_S_Group_New']:
    #         tax = None
    #         if pfb_so_type == 'rent':
    #             tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายยังไม่ถึงกำหนด Vat 7%')], limit=1)
    #         if pfb_so_type == 'sale':
    #             tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายไม่รวม Vat 7%')], limit=1)
    #
    #         if tax:
    #             c_tax_id = [(6, 0, [tax.id])]
    #         else:
    #             c_tax_id = []
    #
    #     elif current_db in ['NPD_Bangkok_New']:
    #         c_tax_id = [(6, 0, [4])]
    #
    #     if current_db in ['test_2025_01','TEST_New','test', 'NPD_S_Group_New_V2', 'NPD_S_Group_New', 'NPD_Bangkok_New']:
    #         # print("เข้า")
    #         if self.second_uom_id and self.second_uom_qty:
    #             # print("เข้า01")
    #             res.update({
    #                 'second_uom_id': self.second_uom_id.id if self.second_uom_id else False,
    #                 'second_uom_qty': self.second_uom_qty or 0.0,
    #                 'discount_type_selection': self.discount_type_selection,
    #                 'tax_ids': c_tax_id,
    #             })
    #         else:
    #             # print("เข้า02")
    #             res.update({
    #                 'discount_type_selection': self.discount_type_selection,
    #                 'tax_ids': c_tax_id,
    #             })
    #     else:
    #         # print("เข้า03")
    #         if self.second_uom_id and self.second_uom_qty:
    #             res.update({
    #                 'second_uom_id': self.second_uom_id.id if self.second_uom_id else False,
    #                 'second_uom_qty': self.second_uom_qty or 0.0,
    #                 'tax_ids': c_tax_id,
    #             })
    #
    #     return res

    def _prepare_invoice_line(self):
        res = super(sale_order_line, self)._prepare_invoice_line()

        current_db = self.env.cr.dbname

        # อ่านแบบปลอดภัย: ถ้า field ไม่มี ให้เป็น False
        pfb_so_type = self.order_id._fields.get('pfb_so_type') and self.order_id.pfb_so_type or False

        c_tax_id = []  # กันเคสหลุดเงื่อนไขแล้ว c_tax_id ไม่ถูกกำหนด

        if current_db in ['test_2025_01', 'TEST_New', 'test', 'NPD_S_Group_New_V2', 'NPD_S_Group_New']:
            tax = None
            if pfb_so_type == 'rent':
                tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายยังไม่ถึงกำหนด Vat 7%')], limit=1)
            elif pfb_so_type == 'sale':
                tax = self.env['account.tax'].search([('name', '=', 'ภาษีขายไม่รวม Vat 7%')], limit=1)

            c_tax_id = [(6, 0, [tax.id])] if tax else []

        elif current_db in ['NPD_Bangkok_New']:
            c_tax_id = [(6, 0, [4])]

        # อัปเดต res ตามเงื่อนไขเดิมของคุณ
        if current_db in ['test_2025_01', 'TEST_New', 'test', 'NPD_S_Group_New_V2', 'NPD_S_Group_New',
                          'NPD_Bangkok_New']:
            if self.second_uom_id and self.second_uom_qty:
                res.update({
                    'second_uom_id': self.second_uom_id.id,
                    'second_uom_qty': self.second_uom_qty or 0.0,
                    'discount_type_selection': self.discount_type_selection,
                    'tax_ids': c_tax_id,
                })
            else:
                res.update({
                    'discount_type_selection': self.discount_type_selection,
                    'tax_ids': c_tax_id,
                })
        else:
            if self.second_uom_id and self.second_uom_qty:
                res.update({
                    'second_uom_id': self.second_uom_id.id,
                    'second_uom_qty': self.second_uom_qty or 0.0,
                    'tax_ids': c_tax_id,
                })

        return res


    @api.onchange('product_id')
    def product_id_change(self):
        res = super(sale_order_line, self).product_id_change()
        if self.product_id:
            self.second_uom_id = self.product_id.second_uom_id and self.product_id.second_uom_id.id or False
            if self.second_uom_id:
                self.second_uom_qty = self.product_uom._compute_quantity(self.product_uom_qty, self.second_uom_id)
        return res

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        res = super(sale_order_line, self).product_uom_change()
        if self.second_uom_id:
            self.second_uom_qty = self.product_uom._compute_quantity(self.product_uom_qty, self.second_uom_id)
        return res

    @api.onchange('second_uom_id', 'second_uom_qty')
    def onchange_dev_product_id(self):
        if self.product_id and self.second_uom_id and self.product_uom:
            if self.second_uom_id:
                self.product_uom_qty = self.second_uom_id._compute_quantity(self.second_uom_qty, self.product_uom)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
