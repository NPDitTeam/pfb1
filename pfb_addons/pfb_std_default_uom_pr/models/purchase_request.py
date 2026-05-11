from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequestLine(models.Model):
    _inherit = "purchase.request.line"

    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UoM",
        tracking=True,
        compute='onchange_domain_product_uom', store=True
    )

    @api.onchange("product_id")
    def onchange_product_id(self):
        if self.product_id:
            name = self.product_id.name
            # if self.product_id.code:
            #     name = "[{}] {}".format(self.product_id.code, name)
            # if self.product_id.description_purchase:
            #     name += "\n" + self.product_id.description_purchase
            self.product_uom_id = self.product_id.uom_po_id.id
            self.product_qty = 1
            self.name = name

    @api.onchange('product_uom_id')
    def onchange_domain_product_uom(self):
        print(self.product_uom_id)
        if self.product_uom_id:
            return {'domain': {'product_uom_id': [('category_id', '=', self.product_uom_id.category_id.id),]},
                    }
