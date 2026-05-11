from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    campaign_id = fields.Many2one(
        'utm.campaign',
        string='แคมเปญการตลาด'
    )
    medium_id = fields.Many2one(
        'utm.medium',
        string='ช่องทางการตลาด'
    )
    source_id = fields.Many2one(
        'utm.source',
        string='แหล่งที่มา'
    )
    customer_channel_id = fields.Many2one(
        'customer.channel',
        string='ลูกค้ามาจากช่องทาง',
        required=True,
    )
    freelance_salesperson_id = fields.Many2one(
        'freelance.salesperson',
        string='เซลล์ Freelance',
    )

    @api.constrains('customer_channel_id')
    def _check_customer_channel_id(self):
        for order in self:
            if not order.customer_channel_id:
                raise ValidationError(_('กรุณากรอกข้อมูล "ลูกค้ามาจากช่องทาง" ที่แท็บการตลาด'))
