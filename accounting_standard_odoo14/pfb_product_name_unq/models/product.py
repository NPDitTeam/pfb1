# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import _, api, fields, models
from odoo.exceptions import UserError,ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.constrains('name')
    def _check_product_name(self):
        Product = self.env["product.template"]
        for rec in self:
            product_id = Product.search(
                [
                    ("name", "=", rec.name),
                ]
            )
            if len(product_id) > 1:
                raise UserError(
                    _(
                        "{} product name already.".format(
                            rec.name
                        )
                    )
                )