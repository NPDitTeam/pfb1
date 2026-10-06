from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # เดิม (โมดูล branch): related="move_id.branch_id" — readonly และถ้าปลด readonly
    # การแก้บรรทัดเดียวจะเขียนกลับไปเปลี่ยนสาขาของหัวเอกสารทั้งใบ
    # เปลี่ยนเป็น compute เก็บค่า + แก้ได้: ค่าเริ่มต้นตามหัวเอกสาร แต่แก้รายบรรทัดได้
    branch_id = fields.Many2one(
        'res.branch', string='Branch', related=False,
        compute='_compute_branch_id', store=True, readonly=False)

    @api.depends('move_id.branch_id')
    def _compute_branch_id(self):
        for line in self:
            line.branch_id = line.move_id.branch_id

    @api.model
    def default_get(self, default_fields):
        # โมดูล branch เติมสาขาเริ่มต้น (สาขาผู้ใช้ หรือค่าว่าง) ให้บรรทัด ตอนเป็น related
        # ค่านี้ไม่มีผล แต่พอเป็นช่องจริงจะถูกนับว่า "ระบุมาแล้ว" ทำให้ไม่ดึงจากหัวเอกสาร
        # ตัดทิ้ง ให้ _compute_branch_id ใช้สาขาของหัวเอกสารเสมอ
        res = super().default_get(default_fields)
        res.pop('branch_id', None)
        return res
