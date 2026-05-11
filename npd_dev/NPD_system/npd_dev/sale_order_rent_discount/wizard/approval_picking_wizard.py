from odoo import models, fields, api


class ApprovalPickingWizard(models.TransientModel):
    _name = 'stock.picking.approval.wizard'
    _description = "Approval Wizard (Stock Picking)"

    picking_id = fields.Many2one('stock.picking', string="Picking", required=True)

    # Fields ที่ต้องมี
    request_note = fields.Text(
        string="หมายเหตุผู้ส่งอนุมัติ",
        readonly=True,
        store=True  # เพิ่ม store=True
    )

    rent_discount = fields.Float(
        string="ยอดส่วนลด",
        readonly=True,
        store=True  # เพิ่ม store=True
    )

    action = fields.Selection([
        ('approve', 'อนุมัติ'),
        ('reject', 'ปฏิเสธ')
    ], string="การพิจารณา", required=True, default='approve')

    approval_note = fields.Text(string="หมายเหตุ", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super(ApprovalPickingWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            picking = self.env['stock.picking'].browse(active_id)
            res.update({
                'picking_id': active_id,
                'request_note': picking.request_note or '',
                'rent_discount': picking.rent_discount or 0.0,
            })
        return res

    def action_process(self):
        if self.action == 'approve':
            self.picking_id.write({
                'approval_state': 'approved',
                'approval_note': self.approval_note,
            })
        else:
            self.picking_id.write({
                'approval_state': 'revise',
                'approval_note': self.approval_note,
            })
        return {'type': 'ir.actions.act_window_close'}