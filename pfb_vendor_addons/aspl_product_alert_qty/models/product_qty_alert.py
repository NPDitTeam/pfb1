# -*- coding: utf-8 -*-
#################################################################################
# Author      : Acespritech Solutions Pvt. Ltd. (<www.acespritech.com>)
# Copyright(c): 2012-Present Acespritech Solutions Pvt. Ltd.
# All Rights Reserved.
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################

from odoo import models, fields, api


class ProductQtyAlert(models.Model):
    _name = "product.qty.alert"

    product_id = fields.Many2one('product.product')
    location_id = fields.Many2one('stock.location', domain=[('usage', '=', 'internal')])
    alert_qty = fields.Float(string="Alert Quantity")


class InheritmailTemplate(models.Model):
    _inherit = "mail.template"

    use_for_alert_qty = fields.Boolean(string="Use For Quantity Alert")


class InheritProduct(models.Model):
    _inherit = "product.product"

    alert_product_ids = fields.One2many('product.qty.alert', 'product_id')
    same_for_all = fields.Boolean(string="Same For All")
    alert_qty = fields.Float(string="Alert Quantity")

    def btn_print_report(self):
        datas = {'form': self.read()[0],
                 'ids': self.id,
                 'model': 'product.product'}
        return self.env.ref('aspl_product_alert_qty.action_report_alert_qty').report_action(self, data=datas)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
