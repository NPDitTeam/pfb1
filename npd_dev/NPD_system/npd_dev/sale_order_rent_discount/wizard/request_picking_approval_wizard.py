from odoo import models, fields, api

class RequestPickingApprovalWizard(models.TransientModel):
    _name = 'stock.picking.request.approval.wizard'
    _description = "Request Approval Wizard (Stock Picking)"

    picking_id = fields.Many2one('stock.picking', required=True)
    approver_id = fields.Many2one( 'res.users', string="ผู้อนุมัติ", required=True, domain=[('is_active', '=', True)] )
    request_note = fields.Text(string="หมายเหตุการขออนุมัติ", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super(RequestPickingApprovalWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            picking = self.env['stock.picking'].browse(active_id)
            res['picking_id'] = active_id
            if picking.approval_state == 'revise' and picking.approver_id:
                res['approver_id'] = picking.approver_id.id
                res['request_note'] = 'แก้ไขตามคำแนะนำแล้ว'
        return res

    def action_send_approval(self):
        self.picking_id.write({
            'approval_state': 'waiting',
            'approver_id': self.approver_id.id,
            'request_note': self.request_note
        })
        return {'type': 'ir.actions.act_window_close'}
