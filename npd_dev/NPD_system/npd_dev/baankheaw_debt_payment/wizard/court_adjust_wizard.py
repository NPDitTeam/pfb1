# -*- coding: utf-8 -*-
"""หน้าต่างเปลี่ยนยอดชำระตามคำสั่งศาล

แสดงยอดเดิมทั้ง 6 ประเภทให้เห็น แล้วให้กรอก "ยอดใหม่" ข้างกัน
ยอดเดิมไม่ถูกแก้ ยอดใหม่ไปเก็บที่ฟิลด์ court_* ของลูกหนี้
"""
from odoo import models, fields, api

DEBT_FIELDS = [
    ('amount', 'ค่าเช่า'),
    ('vat', 'Vat'),
    ('tax', 'Tax'),
    ('lost', 'ค่าปรับหาย'),
    ('broken', 'ค่าปรับชำรุด'),
    ('transport', 'ค่าขนส่ง'),
]


class CourtAdjustWizard(models.TransientModel):
    _name = 'baankheaw.debt_payment_court_wizard'
    _description = 'เปลี่ยนยอดชำระจากศาล'

    summary_id = fields.Many2one('baankheaw.debt_payment', string='ลูกหนี้',
                                 required=True, readonly=True)
    cus_fullname = fields.Char(related='summary_id.cus_fullname', string='ลูกค้า', readonly=True)
    doc_number = fields.Char(related='summary_id.doc_number', string='เลขที่เอกสาร', readonly=True)
    bill_company_name = fields.Char(related='summary_id.bill_company_name', string='บริษัท',
                                    readonly=True)
    line_ids = fields.One2many('baankheaw.debt_payment_court_line', 'wizard_id',
                               string='รายการยอด')
    old_total = fields.Float(string='หนี้รวม (ยอดเดิม)', compute='_compute_totals',
                             digits=(16, 2))
    new_total = fields.Float(string='หนี้รวม (ยอดใหม่)', compute='_compute_totals',
                             digits=(16, 2))
    court_note = fields.Text(string='หมายเหตุคำสั่งศาล')

    @api.depends('line_ids.old_amount', 'line_ids.new_amount')
    def _compute_totals(self):
        for wiz in self:
            wiz.old_total = sum(wiz.line_ids.mapped('old_amount'))
            wiz.new_total = sum(
                line.new_amount if line.is_changed else line.old_amount
                for line in wiz.line_ids
            )

    @api.model
    def default_get(self, fields_list):
        """เปิดหน้าต่างมาให้เห็นยอดเดิมครบทั้ง 6 ประเภททันที

        ถ้าเคยปรับตามศาลไว้แล้ว ช่องยอดใหม่จะเติมค่าที่ปรับไว้ให้ด้วย
        """
        res = super().default_get(fields_list)
        summary_id = res.get('summary_id') or self.env.context.get('default_summary_id')
        if not summary_id:
            return res
        summary = self.env['baankheaw.debt_payment'].browse(summary_id)
        lines = []
        for name, label in DEBT_FIELDS:
            old_value = summary[name] or 0.0
            already_set = summary['court_%s_set' % name]
            lines.append((0, 0, {
                'field_name': name,
                'label': label,
                'old_amount': old_value,
                # ยังไม่เคยปรับ -> ตั้งต้นเท่ายอดเดิม ผู้ใช้แก้เฉพาะช่องที่ศาลสั่ง
                'new_amount': (summary['court_%s' % name] or 0.0) if already_set else old_value,
            }))
        res['line_ids'] = lines
        res['court_note'] = summary.court_note or ''
        return res

    def action_apply(self):
        """บันทึกยอดใหม่ลงฟิลด์ศาล — ยอดเดิมคงไว้เหมือนเดิม"""
        self.ensure_one()
        vals = {'court_note': self.court_note}
        for line in self.line_ids:
            # ช่องที่ไม่ได้แก้ ล้างธงทิ้ง = ใช้ยอดเดิม
            # ช่องที่แก้ ปักธงไว้ แม้ยอดใหม่จะเป็น 0 (ศาลสั่งยกยอดทิ้ง) ก็ยังนับว่าปรับแล้ว
            vals['court_%s' % line.field_name] = (
                line.new_amount if line.is_changed else 0.0)
            vals['court_%s_set' % line.field_name] = line.is_changed
        if any(vals.get('court_%s_set' % name) for name, label in DEBT_FIELDS):
            vals['court_adjust_date'] = fields.Datetime.now()
            vals['court_adjust_uid'] = self.env.uid
        else:
            vals['court_adjust_date'] = False
            vals['court_adjust_uid'] = False
        self.summary_id.write(vals)
        return {'type': 'ir.actions.act_window_close'}


class CourtAdjustWizardLine(models.TransientModel):
    _name = 'baankheaw.debt_payment_court_line'
    _description = 'บรรทัดยอดในหน้าต่างปรับยอดตามศาล'
    _order = 'id'

    wizard_id = fields.Many2one('baankheaw.debt_payment_court_wizard', required=True,
                                ondelete='cascade')
    field_name = fields.Char(string='ฟิลด์', readonly=True)
    label = fields.Char(string='ประเภทยอด', readonly=True)
    old_amount = fields.Float(string='ยอดเดิม', digits=(16, 2), readonly=True)
    new_amount = fields.Float(string='ยอดใหม่ (ตามศาล)', digits=(16, 2))
    is_changed = fields.Boolean(string='ปรับตามศาลสั่ง', compute='_compute_is_changed')
    state_text = fields.Char(string='สถานะ', compute='_compute_is_changed')

    @api.depends('old_amount', 'new_amount')
    def _compute_is_changed(self):
        for line in self:
            changed = abs((line.new_amount or 0.0) - (line.old_amount or 0.0)) > 0.005
            line.is_changed = changed
            line.state_text = 'ปรับตามศาลสั่ง' if changed else 'ใช้ยอดเดิม'
