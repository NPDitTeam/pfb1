from odoo import api, fields, models, tools, exceptions, _
from odoo.osv import expression


class purchase_request_line_report(models.Model):
    _inherit = "purchase.request.line"

    purchased_qty = fields.Float(
        string="RFQ/PO Qty",
        digits="Product Unit of Measure",
        compute="_compute_purchased_qty",
        store=True,
    )

    @api.model
    def incomplete_purchase_request_line_report(self):

        cr = self.env.cr
        sql = ('''
               SELECT  id
               FROM purchase_request_line 
               WHERE  product_qty <> coalesce(purchased_qty, 0) 
            ''')
        cr.execute(sql)
        ids = []
        domain = []
        for row in cr.dictfetchall():
            ids.append(row['id'])
        
        if ids:
            domain = [('id','in', ids)]
        return {
            'name': _('Incomplete Purchase Request Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.request.line',
            'view_mode': 'tree,pivot,graph',
            'domain': domain,
        }




