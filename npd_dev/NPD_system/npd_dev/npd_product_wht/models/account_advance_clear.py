# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AdvanceClearLine(models.Model):
    _inherit = 'advance.clear.line'

    wht_category_id = fields.Many2one(
        comodel_name='wht.category',
        string='หมวดหมู่ WHT',
        help='หมวดหมู่ภาษีหัก ณ ที่จ่าย',
    )
    wht_rate_display = fields.Char(
        string='อัตรา WHT',
        compute='_compute_wht_rate_display',
    )
    is_deduct_vat = fields.Boolean(
        string='หัก VAT',
        default=False,
        help='ถ้าติ๊ก ระบบจะถอด VAT 7% จาก Unit Price ก่อนส่งไปสร้าง WHT (เฉพาะ db NPD_Logistics_New)',
    )
    wht_total = fields.Float(
        string='Withholding Tax',
        compute='_compute_wht_total',
        store=True,
        digits=(16, 2),
    )
    wht_status = fields.Selection(
        selection=[
            ('eligible', 'ใช้ WHT ได้'),
            ('no_category', 'ยังไม่เลือกหมวดหมู่ WHT'),
        ],
        string='สถานะ WHT',
        compute='_compute_wht_status',
    )

    @api.depends('wht_category_id')
    def _compute_wht_status(self):
        """สถานะ WHT ต่อ line: เช็คเฉพาะว่าเลือกหมวดหมู่ WHT และ rate > 0"""
        for line in self:
            if not line.wht_category_id or line.wht_category_id.wht_rate == '0':
                line.wht_status = 'no_category'
            else:
                line.wht_status = 'eligible'

    @api.depends('wht_category_id', 'price_unit', 'quantity',
                 'tax_ids', 'is_deduct_vat')
    def _compute_wht_total(self):
        """คำนวณ wht_total ต่อ line:
        - db NPD_Logistics_New → ใช้ _get_wht_base_amount (รองรับหัก VAT 7%)
        - db อื่น → ใช้ price_subtotal (ยอดก่อน VAT)
        """
        is_target_db = self.env.cr.dbname == 'NPD_Logistics_New'
        for line in self:
            if line.wht_category_id and line.wht_category_id.wht_rate != '0':
                rate = line.wht_category_id.wht_rate_float
                if is_target_db:
                    base = line._get_wht_base_amount()
                else:
                    base = line.price_subtotal
                line.wht_total = round(base * rate / 100.0, 2)
            else:
                line.wht_total = 0.0

    def _get_wht_base_amount(self):
        """คำนวณยอดที่ใช้เป็น base ของ WHT
        - db NPD_Logistics_New + is_deduct_vat=True → round(price_unit / 1.07, 2)
        - db NPD_Logistics_New + is_deduct_vat=False → price_unit
        - db อื่น → price_subtotal (เดิม)
        round เป็น 2 ตำแหน่ง เพื่อเลี่ยง float precision error ในการเช็ค threshold
        """
        self.ensure_one()
        if self.env.cr.dbname == 'NPD_Logistics_New':
            if self.is_deduct_vat:
                return round(self.price_unit / 1.07, 2)
            return self.price_unit
        return self.price_subtotal

    @api.depends('wht_category_id')
    def _compute_wht_rate_display(self):
        for line in self:
            if line.wht_category_id:
                line.wht_rate_display = '%s%%' % line.wht_category_id.wht_rate
            else:
                line.wht_rate_display = ''

    @api.onchange('product_id')
    def _onchange_product_wht(self):
        """เมื่อเลือกสินค้า ให้ดึงหมวดหมู่ WHT จากสินค้า"""
        if self.product_id and self.product_id.product_tmpl_id.wht_category_id:
            self.wht_category_id = self.product_id.product_tmpl_id.wht_category_id.id


class AccountAdvanceClear(models.Model):
    _inherit = 'account.advance.clear'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form',
                        toolbar=False, submenu=False):
        res = super().fields_view_get(
            view_id=view_id, view_type=view_type,
            toolbar=toolbar, submenu=submenu,
        )
        # ซ่อน column is_deduct_vat ถ้าไม่ใช่ db NPD_Logistics_New
        if view_type == 'form' and self.env.cr.dbname != 'NPD_Logistics_New':
            from lxml import etree
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='clear_ids']/tree/field[@name='is_deduct_vat']"):
                node.getparent().remove(node)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    def _remove_wht_cert_ids(self, cert_ids):
        """ลบ WHT cert ตาม id ที่ระบุ ผ่าน SQL เพื่อไม่ trigger compute"""
        if not cert_ids:
            return
        self.env.cr.execute(
            "DELETE FROM withholding_tax_cert_line WHERE cert_id IN %s",
            (tuple(cert_ids),)
        )
        self.env.cr.execute(
            "DELETE FROM withholding_tax_cert WHERE id IN %s",
            (tuple(cert_ids),)
        )
        self.invalidate_cache()

    def _set_wht_certs_draft(self):
        """set WHT cert ทุกใบของ advance clear นี้ เป็น draft ผ่าน SQL"""
        for rec in self:
            cert_ids = rec.wt_cert_ids.ids
            if cert_ids:
                self.env.cr.execute(
                    "UPDATE withholding_tax_cert SET state = 'draft' WHERE id IN %s",
                    (tuple(cert_ids),)
                )
                self.invalidate_cache()

    def _check_wht_cert_before_post(self):
        """ตรวจสอบก่อน Post:
        - ถ้ามี line ที่ wht_status='eligible' แต่ยังไม่ได้เลือกคู่ค้า → แจ้งเตือน
        - ถ้ามี line ที่ wht_status='eligible' แต่ยังไม่ได้สร้าง WHT cert
          ที่ match (partner, date, rate) → แจ้งเตือนให้กดปุ่ม "สร้าง WHT อัตโนมัติ"
        """
        self.ensure_one()
        doc_date = self.doc_date or fields.Date.today()

        # รวบรวม key ของ line ที่ต้องมี cert
        needs_cert = {}  # (partner_id, date, rate_float) -> [lines]
        no_partner_lines = []
        for line in self.clear_ids:
            if line.wht_status != 'eligible':
                continue
            if not line.partner_id:
                no_partner_lines.append(line)
                continue
            key = (
                line.partner_id.id,
                line.invoice_date or doc_date,
                line.wht_category_id.wht_rate_float,
            )
            needs_cert.setdefault(key, []).append(line)

        # รวบรวม key ของ cert ที่มีอยู่แล้ว
        existing = set()
        for cert in self.wt_cert_ids:
            for cl in cert.wt_line:
                existing.add(
                    (cert.supplier_partner_id.id, cert.date, cl.wt_percent)
                )

        missing = [
            line for key, lines in needs_cert.items()
            if key not in existing
            for line in lines
        ]

        if not missing and not no_partner_lines:
            return

        msgs = []
        if no_partner_lines:
            msgs.append(_('⚠ รายการที่ใช้ WHT ได้ แต่ยังไม่ได้เลือกคู่ค้า:'))
            for line in no_partner_lines:
                msgs.append('  • %s (ยอด %s บาท)' % (
                    line.product_id.name or line.name or '-',
                    '{:,.2f}'.format(line._get_wht_base_amount()),
                ))
        if missing:
            if msgs:
                msgs.append('')
            msgs.append(_('⚠ รายการที่ใช้ WHT ได้ แต่ยังไม่สร้าง Withholding Tax:'))
            for line in missing:
                msgs.append('  • %s | %s (ยอด %s บาท)' % (
                    line.partner_id.name or '-',
                    line.product_id.name or line.name or '-',
                    '{:,.2f}'.format(line._get_wht_base_amount()),
                ))
            msgs.append('')
            msgs.append(_('กรุณากดปุ่ม "สร้าง WHT อัตโนมัติ" ก่อน Post'))

        raise UserError('\n'.join(msgs))

    def confirm(self):
        """Override: เช็ค WHT ก่อน Post"""
        for rec in self:
            rec._check_wht_cert_before_post()
        return super(AccountAdvanceClear, self).confirm()

    def set_draft(self):
        """Override: set WHT cert เป็น draft (ไม่ลบ เพื่อรักษาเลขรัน)"""
        self._set_wht_certs_draft()
        return super(AccountAdvanceClear, self).set_draft()

    def action_cancel_draft(self):
        """Override: set WHT cert เป็น draft (ไม่ลบ เพื่อรักษาเลขรัน)"""
        self._set_wht_certs_draft()
        return super(AccountAdvanceClear, self).action_cancel_draft()

    def cancel_advance(self):
        """Override: set WHT cert เป็น draft (ไม่ลบ เพื่อรักษาเลขรัน)"""
        self._set_wht_certs_draft()
        return super(AccountAdvanceClear, self).cancel_advance()

    def _get_past_total(self, partner_id, product_id, doc_date):
        """
        ดึงยอดย้อนหลัง 1 ปี เฉพาะ state = post
        ของ Partner (คู่ค้า) + Product เดียวกัน
        ใช้ _get_wht_base_amount เพื่อให้ถอด VAT 7% หาก is_deduct_vat=True
        """
        date_from = doc_date - timedelta(days=365)
        domain = [
            ('partner_id', '=', partner_id),
            ('product_id', '=', product_id),
            ('advance_clear_id.doc_date', '>=', date_from),
            ('advance_clear_id.doc_date', '<=', doc_date),
            ('advance_clear_id.state', '=', 'post'),
        ]
        past_lines = self.env['advance.clear.line'].search(domain)
        return sum(line._get_wht_base_amount() for line in past_lines)

    def action_auto_create_wht_cert(self):
        """
        สร้าง/อัพเดท Withholding Tax Certificate อัตโนมัติจากข้อมูล advance clear lines
        ทุก line ที่มีหมวดหมู่ WHT + rate > 0 + partner + product → สร้าง cert
        ถ้า partner เดิมมี cert อยู่แล้ว -> update ใช้เลขรันเดิม
        ถ้า partner เดิมไม่มี line ที่เข้าเกณฑ์ -> ลบ cert ของ partner นั้น
        """
        for rec in self:
            doc_date = rec.doc_date or fields.Date.today()

            # รวบรวม line ที่เข้าเกณฑ์ (มีหมวดหมู่ + rate + partner + product)
            passed_lines = []
            for line in rec.clear_ids:
                if not line.wht_category_id or line.wht_category_id.wht_rate == '0':
                    continue
                if not line.product_id:
                    continue
                if not line.partner_id:
                    continue
                passed_lines.append(line)
            skipped_products = []

            # ขั้นตอน 3: สร้าง WHT cert จาก lines ที่ผ่านเกณฑ์
            # key = (partner_id, invoice_date, wht_rate) → แยก cert ต่อ invoice_date
            wht_data = {}
            for line in passed_lines:
                partner = line.partner_id or self.env.user.company_id.partner_id
                wht_cat = line.wht_category_id
                line_date = line.invoice_date or doc_date
                key = (partner.id, line_date, wht_cat.wht_rate)

                if key not in wht_data:
                    wht_data[key] = {
                        'partner': partner,
                        'wht_cat': wht_cat,
                        'date': line_date,
                        'base': 0.0,
                    }
                wht_data[key]['base'] += line._get_wht_base_amount()

            if not wht_data:
                return True
            if skipped_products:
                warning_msg = _(
                    'หมายเหตุ: ข้ามรายการต่อไปนี้เนื่องจากยอดรวม 1 ปี ไม่ถึง 1,000 บาท:\n%s'
                ) % '\n'.join(skipped_products)

            # จัดกลุ่ม wht_data ต่อ (partner, invoice_date)
            partner_groups = {}
            for key, data in wht_data.items():
                pid = data['partner'].id
                gkey = (pid, data['date'])
                partner_groups.setdefault(gkey, []).append((key, data))

            # หา cert เดิมที่ผูกอยู่ จัดกลุ่มตาม (partner, date)
            existing_certs_by_key = {}
            for cert in rec.wt_cert_ids.sorted('id'):
                ckey = (cert.supplier_partner_id.id, cert.date)
                existing_certs_by_key.setdefault(
                    ckey, self.env['withholding.tax.cert']
                )
                existing_certs_by_key[ckey] |= cert

            # cert ที่ (partner, date) เดิมหายไปจาก lines → เอามา recycle
            # (เพื่อรักษาเลขรัน ไม่สร้างใหม่/ไม่เกิด gap)
            recyclable_certs = self.env['withholding.tax.cert']
            keys_no_longer = set(existing_certs_by_key.keys()) - set(partner_groups.keys())
            for ckey in keys_no_longer:
                recyclable_certs |= existing_certs_by_key[ckey]
            recyclable_certs = recyclable_certs.sorted('id')

            # (partner, date) ใหม่ที่ยังไม่มี cert
            new_keys = [
                gkey for gkey in partner_groups.keys()
                if gkey not in existing_certs_by_key
            ]

            # จับคู่ recycle: ใส่ cert เก่าเข้า map ของ key ใหม่ตามลำดับ
            recycle_map = {}  # new_key -> existing_cert
            recyclable_iter = iter(recyclable_certs)
            for new_key in new_keys:
                cert = next(recyclable_iter, None)
                if cert is None:
                    break
                recycle_map[new_key] = cert
                # เพิ่มเข้า existing_certs_by_key เพื่อให้ flow ด้านล่าง update เหมือน key เดิม
                existing_certs_by_key[new_key] = cert

            # cert เก่าที่ยัง recycle ไม่หมด → ลบ
            recycled_ids = set(c.id for c in recycle_map.values())
            cert_ids_to_delete = [
                c.id for c in recyclable_certs if c.id not in recycled_ids
            ]
            if cert_ids_to_delete:
                rec._remove_wht_cert_ids(cert_ids_to_delete)

            company = rec.company_id
            new_certs = []
            for gkey, entries in partner_groups.items():
                partner = entries[0][1]['partner']
                cert_date = entries[0][1]['date']
                if partner.company_type == 'company':
                    income_tax_form = 'pnd53'
                else:
                    income_tax_form = 'pnd3'

                account_id = False
                if income_tax_form == 'pnd53':
                    account_id = company.account_pnd53_withholding_tax_id.id
                elif income_tax_form == 'pnd3':
                    account_id = company.account_pnd3_withholding_tax_id.id
                if not account_id:
                    account_id = company.account_withholding_tax_id.id

                cert_lines = []
                for key, data in entries:
                    wht_cat = data['wht_cat']
                    rate = wht_cat.wht_rate_float
                    base = data['base']
                    income_desc = wht_cat.income_description or wht_cat.name
                    cert_lines.append({
                        'wt_cert_income_type': '6',
                        'wt_cert_income_desc': income_desc,
                        'base': base,
                        'wt_percent': rate,
                        'amount': base * rate / 100.0,
                    })

                if gkey in existing_certs_by_key:
                    # update cert เดิม - คงเลขรันเดิม
                    existing_cert = existing_certs_by_key[gkey][0]
                    # ถ้ามี cert ของ key นี้มากกว่า 1 ใบ ลบที่เกินทิ้ง (เก็บใบแรก)
                    extra_cert_ids = existing_certs_by_key[gkey][1:].ids
                    if extra_cert_ids:
                        rec._remove_wht_cert_ids(extra_cert_ids)
                    # set กลับเป็น draft ก่อน เพื่อให้ field ที่ readonly เมื่อ done เขียนได้
                    self.env.cr.execute(
                        "UPDATE withholding_tax_cert SET state = 'draft' WHERE id = %s",
                        (existing_cert.id,)
                    )
                    # ลบ line เก่าทั้งหมดผ่าน SQL
                    self.env.cr.execute(
                        "DELETE FROM withholding_tax_cert_line WHERE cert_id = %s",
                        (existing_cert.id,)
                    )
                    self.invalidate_cache()
                    update_vals = {
                        'supplier_partner_id': partner.id,
                        'income_tax_form': income_tax_form,
                        'date': cert_date,
                        'tax_payer': 'withholding',
                        'wt_line': [(0, 0, line) for line in cert_lines],
                    }
                    if account_id:
                        update_vals['account_id'] = account_id
                    if rec.branch_id:
                        update_vals['branch_id'] = rec.branch_id.id
                    existing_cert.write(update_vals)
                    # set กลับเป็น done
                    self.env.cr.execute(
                        "UPDATE withholding_tax_cert SET state = 'done' WHERE id = %s",
                        (existing_cert.id,)
                    )
                else:
                    # key ใหม่ - สร้าง cert พร้อมขอเลขรันใหม่
                    seq_ids = self.env['ir.sequence'].search(
                        [('code', '=', 'withholding.tax'),
                         ('company_id', '=', company.id)],
                        order='company_id', limit=1,
                    )
                    if seq_ids:
                        cert_name = seq_ids[0].next_by_id(sequence_date=cert_date)
                    else:
                        cert_name = self.env['ir.sequence'].next_by_code('withholding.tax')

                    cert_vals = {
                        'name': cert_name,
                        'supplier_partner_id': partner.id,
                        'income_tax_form': income_tax_form,
                        'date': cert_date,
                        'tax_payer': 'withholding',
                        'wt_line': [(0, 0, line) for line in cert_lines],
                    }
                    if account_id:
                        cert_vals['account_id'] = account_id
                    if rec.branch_id:
                        cert_vals['branch_id'] = rec.branch_id.id
                    new_certs.append((0, 0, cert_vals))

            if new_certs:
                rec.write({'wt_cert_ids': new_certs})
            # set state done สำหรับ cert ที่ยังเป็น draft
            for cert in rec.wt_cert_ids.filtered(lambda c: c.state == 'draft'):
                self.env.cr.execute(
                    "UPDATE withholding_tax_cert SET state = 'done' WHERE id = %s",
                    (cert.id,)
                )
            rec.invalidate_cache(['wt_cert_ids'])

        return True
