from odoo import models, fields, api

class StockRequest(models.Model):
    _inherit = 'stock.request'

    location_src_id = fields.Many2one(
        'stock.location',
        string='ตำแหน่งตั้งต้น',
        domain=[],
        required=True
    )

    @api.onchange('route_id', 'location_id')
    def _onchange_route_id_set_location_domain(self):
        for rec in self:
            if rec.route_id and rec.location_id:
                # กรอง rule ตามปลายทาง
                rules = rec.route_id.rule_ids.filtered(
                    lambda r: r.location_id and r.location_id.id == rec.location_id.id
                )

                # ดึง location_src_id ทั้งหมดที่ตรงเงื่อนไข
                location_ids = rules.filtered(lambda r: r.location_src_id).mapped('location_src_id').ids

                # กำหนด domain
                domain = {'location_src_id': [('id', 'in', location_ids)]}

                # ✅ Auto select ค่าตัวแรก
                if location_ids:
                    rec.location_src_id = location_ids[0]
                else:
                    rec.location_src_id = False

                return {'domain': domain}
            else:
                rec.location_src_id = False
                return {'domain': {'location_src_id': []}}
