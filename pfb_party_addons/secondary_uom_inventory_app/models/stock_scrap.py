# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    secondary_uom_id = fields.Many2one('uom.uom',  string="Secondary UOM",compute="_quantity_compute_scrap",store=True)
    secondary_quantity = fields.Float(string='Secondary Qty',compute="_quantity_compute_scrap",store=True)


    @api.depends('product_id', 'scrap_qty')
    def _quantity_compute_scrap(self):
        for scrap in self:
            if scrap.product_id.is_secondary_uom:
                uom_quantity = scrap.scrap_qty#scrap.product_id.uom_id._compute_quantity(scrap.scrap_qty, scrap.product_id.secondary_uom_id, rounding_method='HALF-UP')
                scrap.update({'secondary_uom_id' : scrap.product_id.secondary_uom_id})
                scrap.update({'secondary_quantity' : uom_quantity})

