# -*- coding: utf-8 -*-
import calendar
import re
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

MONTHS = [(str(i), name) for i, name in enumerate(
    [u'มกราคม', u'กุมภาพันธ์', u'มีนาคม', u'เมษายน', u'พฤษภาคม', u'มิถุนายน', u'กรกฎาคม',
     u'สิงหาคม', u'กันยายน', u'ตุลาคม', u'พฤศจิกายน', u'ธันวาคม'], 1)]
PREVIEW_LIMIT = 2000


class NpdVatSplitFixWizard(models.TransientModel):
    _name = 'npd.vat.split.fix.wizard'
    _description = 'ตรวจและแก้ฐาน/VAT ไม่ตรงยอดรวม'

    def _default_year(self):
        return self.env['npd.vat.split.fix']._thai_today().year

    def _default_month(self):
        return str(self.env['npd.vat.split.fix']._thai_today().month)

    scope = fields.Selection([('numbers', 'เฉพาะเลขที่ที่ระบุ'), ('all', 'ทั้งหมดที่คำนวณไม่ถูกต้อง')],
                             string='แก้', default='numbers', required=True)
    numbers = fields.Text('เลขที่เอกสาร',
                          help='ใส่ได้หลายเลข คั่นด้วยเว้นวรรค จุลภาค หรือขึ้นบรรทัดใหม่ เช่น CN-1019260004')
    period = fields.Selection([('month', 'เลือกเดือน'), ('all', 'ทุกเดือน')], string='ช่วงเวลา',
                              default='month', required=True)
    month = fields.Selection(MONTHS, string='เดือน', default=_default_month)
    year = fields.Integer('ปี (ค.ศ.)', default=_default_year)
    include_invoice = fields.Boolean('ใบแจ้งหนี้', default=True)
    include_refund = fields.Boolean('ใบลดหนี้', default=True)
    min_diff = fields.Float('ส่วนต่างขั้นต่ำ (บาท)', default=0.01, digits=(16, 2),
                            help='แก้เฉพาะใบที่ยอดก่อน VAT ต่างจาก ยอดรวม ÷ 1.07 ตั้งแต่ยอดนี้ขึ้นไป')
    state = fields.Selection([('draft', 'เลือก'), ('preview', 'ตรวจ'), ('done', 'เสร็จ')], default='draft')
    line_ids = fields.One2many('npd.vat.split.fix.wizard.line', 'wizard_id', string='รายการ')
    count_fix = fields.Integer(compute='_compute_counts', string='แก้ได้')
    count_skip = fields.Integer(compute='_compute_counts', string='ข้าม')
    summary = fields.Text('สรุป', readonly=True)

    @api.depends('line_ids.status')
    def _compute_counts(self):
        for wiz in self:
            wiz.count_fix = len(wiz.line_ids.filtered(lambda l: l.status == 'fix'))
            wiz.count_skip = len(wiz.line_ids.filtered(lambda l: l.status == 'skip'))

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new', 'name': _('ตรวจและแก้ฐาน/VAT ไม่ตรงยอดรวม')}

    def _dates(self):
        if self.period != 'month':
            return None, None
        if not self.month or not self.year:
            raise UserError(_('กรุณาเลือกเดือนและปี'))
        m, y = int(self.month), int(self.year)
        if y > 2400:            # ใส่ปี พ.ศ. มา
            y -= 543
        return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])

    def _names(self):
        if self.scope != 'numbers':
            return None
        names = [n for n in re.split(r'[\s,;]+', self.numbers or '') if n]
        if not names:
            raise UserError(_('กรุณาใส่เลขที่เอกสาร'))
        return names

    def action_search(self):
        self.ensure_one()
        types = [t for t, on in (('out_invoice', self.include_invoice), ('out_refund', self.include_refund)) if on]
        if not types:
            raise UserError(_('กรุณาเลือกอย่างน้อย ใบแจ้งหนี้ หรือ ใบลดหนี้'))
        date_from, date_to = self._dates()
        names = self._names()
        engine = self.env['npd.vat.split.fix']
        ids = engine.find_candidates(date_from=date_from, date_to=date_to, names=names,
                                     move_types=types, min_diff=self.min_diff)
        self.line_ids.unlink()
        vals = []
        Move = self.env['account.move'].sudo()
        for move in Move.browse(ids[:PREVIEW_LIMIT]):
            plan, reason = engine.analyze(move)
            vals.append({
                'wizard_id': self.id, 'move_id': move.id,
                'total': move.amount_total, 'old_base': move.amount_untaxed, 'old_tax': move.amount_tax,
                'new_base': float(plan['new_base']) if plan else 0.0,
                'new_tax': float(plan['new_tax']) if plan else 0.0,
                'status': 'skip' if reason else 'fix', 'reason': reason or '',
                'selected': not reason,
            })
        self.env['npd.vat.split.fix.wizard.line'].create(vals)
        summary = _(u'พบ %s ใบที่ยอดก่อน VAT ไม่เท่ายอดรวม ÷ 1.07') % len(ids)
        if names:
            found = set(Move.browse(ids).mapped('name'))
            missing = [n for n in names if n not in found]
            if missing:
                summary += _(u'\nไม่พบ/คำนวณถูกอยู่แล้ว: %s') % ', '.join(missing)
        if len(ids) > PREVIEW_LIMIT:
            summary += _(u'\nแสดง %s ใบแรก กดแก้แล้วค้นหาซ้ำเพื่อทำชุดถัดไป') % PREVIEW_LIMIT
        self.write({'state': 'preview', 'summary': summary})
        return self._reopen()

    def action_apply(self):
        self.ensure_one()
        engine = self.env['npd.vat.split.fix']
        targets = self.line_ids.filtered(lambda l: l.selected and l.status == 'fix')
        if not targets:
            raise UserError(_('ไม่มีรายการที่เลือกให้แก้'))
        done = failed = 0
        for line in targets:
            try:
                with self.env.cr.savepoint():
                    log = engine.apply(line.move_id, source='manual')
                line.write({'status': 'done', 'reason': _('แก้แล้ว') if log else _('ถูกต้องอยู่แล้ว'),
                            'log_id': log.id if log else False})
                done += 1
            except Exception as e:
                line.write({'status': 'error', 'reason': str(e)[:500]})
                failed += 1
        self.write({'state': 'done',
                    'summary': (self.summary or '') + _(u'\n\nแก้สำเร็จ %s ใบ, ไม่สำเร็จ %s ใบ') % (done, failed)})
        return self._reopen()

    def action_back(self):
        self.ensure_one()
        self.line_ids.unlink()
        self.write({'state': 'draft', 'summary': False})
        return self._reopen()

    def action_select_all(self):
        self.line_ids.filtered(lambda l: l.status == 'fix').write({'selected': True})
        return self._reopen()

    def action_select_none(self):
        self.line_ids.write({'selected': False})
        return self._reopen()

    def action_open_log(self):
        action = self.env.ref('npd_vat_split_fix.action_npd_vat_split_fix_log').read()[0]
        action['domain'] = [('id', 'in', self.line_ids.mapped('log_id').ids)]
        return action


class NpdVatSplitFixWizardLine(models.TransientModel):
    _name = 'npd.vat.split.fix.wizard.line'
    _description = 'รายการตรวจฐาน/VAT'
    _order = 'status desc, move_date, id'

    wizard_id = fields.Many2one('npd.vat.split.fix.wizard', required=True, ondelete='cascade')
    selected = fields.Boolean('เลือก', default=True)
    move_id = fields.Many2one('account.move', string='เลขที่', readonly=True)
    move_type = fields.Selection(related='move_id.move_type', string='ประเภท')
    move_date = fields.Date(related='move_id.date', string='วันที่', store=True)
    partner_id = fields.Many2one(related='move_id.partner_id', string='ลูกค้า')
    total = fields.Float('ยอดรวม', digits=(16, 2), readonly=True)
    old_base = fields.Float('ฐานเดิม', digits=(16, 2), readonly=True)
    old_tax = fields.Float('VAT เดิม', digits=(16, 2), readonly=True)
    new_base = fields.Float('ฐานใหม่', digits=(16, 2), readonly=True)
    new_tax = fields.Float('VAT ใหม่', digits=(16, 2), readonly=True)
    diff = fields.Float('ส่วนต่างฐาน', digits=(16, 2), compute='_compute_diff')
    status = fields.Selection([('fix', 'แก้ได้'), ('skip', 'ข้าม'), ('done', 'แก้แล้ว'), ('error', 'ไม่สำเร็จ')],
                              string='สถานะ', readonly=True)
    reason = fields.Char('หมายเหตุ', readonly=True)
    log_id = fields.Many2one('npd.vat.split.fix.log', readonly=True)

    @api.depends('old_base', 'new_base', 'status')
    def _compute_diff(self):
        for line in self:
            line.diff = line.new_base - line.old_base if line.status != 'skip' else 0.0
