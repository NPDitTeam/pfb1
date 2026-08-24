# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AccountVoucherLine(models.Model):
    _inherit = 'account.voucher.line'

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
        """เมื่อเลือกสินค้า ให้ดึงหมวดหมู่ WHT จากสินค้า และคำนวณ wht_total"""
        if self.product_id and self.product_id.product_tmpl_id.wht_category_id:
            self.wht_category_id = self.product_id.product_tmpl_id.wht_category_id.id
        self._calc_wht_total()

    @api.onchange('wht_category_id', 'price_unit', 'quantity', 'tax_ids', 'is_deduct_vat')
    def _onchange_wht_total(self):
        """คำนวณ wht_total เมื่อเปลี่ยนหมวดหมู่ WHT, จำนวนเงิน, หรือหัก VAT"""
        self._calc_wht_total()

    def _calc_wht_total(self):
        """คำนวณ wht_total
        - db NPD_Logistics_New → ใช้ _get_wht_base_amount (รองรับหัก VAT 7%)
        - db อื่น → ใช้ ยอดก่อน VAT (เดิม)
        """
        if self.wht_category_id and self.wht_category_id.wht_rate != '0':
            rate = self.wht_category_id.wht_rate_float
            if self.env.cr.dbname == 'NPD_Logistics_New':
                base = self._get_wht_base_amount()
            else:
                # db อื่น: คำนวณยอดก่อน VAT จาก tax_ids
                if self.tax_ids:
                    taxes = self.tax_ids.compute_all(
                        self.price_unit,
                        self.voucher_id.currency_id,
                        self.quantity,
                        product=self.product_id,
                    )
                    base = taxes['total_excluded']
                else:
                    base = self.price_unit * self.quantity
            self.wht_total = round(base * rate / 100.0, 2)
        else:
            self.wht_total = 0.0


class AccountVoucher(models.Model):
    _inherit = 'account.voucher'

    # ยอดที่จ่ายออกจากธนาคารจริง = ยอดบิล - ภาษีหัก ณ ที่จ่าย
    # ฟอร์มเดิมโชว์แค่ "รวม" ซึ่งเป็นยอดก่อนหัก ทำให้ต้องคิดในใจทุกครั้งว่าจะโอนเท่าไหร่
    # ตัวเลขนี้ตรงกับบรรทัดธนาคารในสมุดรายวันที่ account_voucher.first_move_line_get()
    # สร้างด้วยสูตรเดียวกัน (abs(amount - wht_amount)) จึงไม่กระทบการลงบัญชีใด ๆ
    net_payment_amount = fields.Monetary(
        string='ยอดจ่ายสุทธิ',
        currency_field='currency_id',
        compute='_compute_net_payment_amount',
        help='ยอดที่จ่าย/รับจริงหลังหักภาษี ณ ที่จ่ายแล้ว (รวม - Withholding Tax)',
    )

    @api.depends('amount', 'wht_amount')
    def _compute_net_payment_amount(self):
        for voucher in self:
            voucher.net_payment_amount = (voucher.amount or 0.0) - (voucher.wht_amount or 0.0)

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
            for node in doc.xpath("//field[@name='line_ids']/tree/field[@name='is_deduct_vat']"):
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
        """set WHT cert ทุกใบของ voucher นี้ เป็น draft ผ่าน SQL"""
        for rec in self:
            cert_ids = rec.wt_cert_ids.ids
            if cert_ids:
                self.env.cr.execute(
                    "UPDATE withholding_tax_cert SET state = 'draft' WHERE id IN %s",
                    (tuple(cert_ids),)
                )
                self.invalidate_cache()

    def _check_wht_cert_before_validate(self):
        """ตรวจสอบก่อนกดปุ่ม ตรวจสอบ (proforma_voucher):
        - ทำงานเฉพาะเมื่อ check_type_show_selection == 'false'
          (ตรง condition เดียวกับปุ่ม "สร้าง WHT อัตโนมัติ")
        - ถ้ามี line ที่ wht_status='eligible' แต่ voucher ยังไม่ได้เลือกคู่ค้า → เตือน
        - ถ้ามี line ที่ wht_status='eligible' แต่ยังไม่มี WHT cert
          ที่ match rate → เตือนให้กด "สร้าง WHT อัตโนมัติ"
        """
        self.ensure_one()

        # ข้ามเช็คถ้า check_type_show_selection ไม่ใช่ 'false'
        if self.check_type_show_selection != 'false':
            return

        # รวบรวม line eligible ต่อ rate (voucher 1 ใบ = 1 partner)
        needs_cert_rates = {}  # rate_str -> [lines]
        for line in self.line_ids:
            if line.wht_status != 'eligible':
                continue
            rate_str = line.wht_category_id.wht_rate
            needs_cert_rates.setdefault(rate_str, []).append(line)

        if not needs_cert_rates:
            return

        # voucher ต้องมี partner (ไม่มี → สร้าง cert ไม่ได้)
        if not self.partner_id:
            all_lines = [l for ls in needs_cert_rates.values() for l in ls]
            msgs = [_('⚠ รายการใช้ WHT ได้ แต่ยังไม่ได้เลือกคู่ค้า:')]
            for line in all_lines:
                msgs.append('  • %s (ยอด %s บาท)' % (
                    line.product_id.name or line.name or '-',
                    '{:,.2f}'.format(line._get_wht_base_amount()),
                ))
            raise UserError('\n'.join(msgs))

        # rate ที่มี cert แล้ว
        existing_rates = set()
        for cert in self.wt_cert_ids:
            first_line = cert.wt_line[:1]
            if first_line:
                existing_rates.add('%g' % first_line.wt_percent)

        missing_lines = []
        for rate_str, lines in needs_cert_rates.items():
            if rate_str not in existing_rates:
                missing_lines.extend(lines)

        if not missing_lines:
            return

        msgs = [_('⚠ รายการที่ใช้ WHT ได้ แต่ยังไม่สร้าง Withholding Tax:')]
        for line in missing_lines:
            msgs.append('  • %s (ยอด %s บาท)' % (
                line.product_id.name or line.name or '-',
                '{:,.2f}'.format(line._get_wht_base_amount()),
            ))
        msgs.append('')
        msgs.append(_('กรุณากดปุ่ม "สร้าง WHT อัตโนมัติ" ก่อนตรวจสอบ'))

        raise UserError('\n'.join(msgs))

    def proforma_voucher(self):
        """Override: เช็ค WHT ก่อนกดปุ่ม ตรวจสอบ"""
        for rec in self:
            rec._check_wht_cert_before_validate()
        return super(AccountVoucher, self).proforma_voucher()

    def cancel_voucher(self):
        """Override: set WHT cert เป็น draft (ไม่ลบ เพื่อรักษาเลขรัน)"""
        self._set_wht_certs_draft()
        return super(AccountVoucher, self).cancel_voucher()

    def action_cancel_draft(self):
        """Override: set WHT cert เป็น draft (ไม่ลบ เพื่อรักษาเลขรัน)"""
        self._set_wht_certs_draft()
        return super(AccountVoucher, self).action_cancel_draft()

    def _get_voucher_past_total(self, partner_id, product_id, doc_date):
        """
        ดึงยอดย้อนหลัง 1 ปี เฉพาะ state = posted
        ของ Partner + Product เดียวกัน
        ใช้ _get_wht_base_amount เพื่อให้ถอด VAT 7% หาก is_deduct_vat=True
        """
        date_from = doc_date - timedelta(days=365)
        domain = [
            ('voucher_id.partner_id', '=', partner_id),
            ('product_id', '=', product_id),
            ('voucher_id.date', '>=', date_from),
            ('voucher_id.date', '<=', doc_date),
            ('voucher_id.state', '=', 'posted'),
        ]
        past_lines = self.env['account.voucher.line'].search(domain)
        return sum(line._get_wht_base_amount() for line in past_lines)

    def action_auto_create_wht_cert(self):
        """
        สร้าง/อัพเดท Withholding Tax Certificate อัตโนมัติจากข้อมูล voucher lines
        ทุก line ที่มีหมวดหมู่ WHT + rate > 0 + product → สร้าง cert
        ถ้ามี cert อยู่แล้ว -> update ใช้เลขรันเดิม
        ถ้า key เดิมไม่มี line ที่เข้าเกณฑ์ -> ลบ cert / recycle ให้ key ใหม่
        """
        for rec in self:
            # อัปเดต wht_total บนทุก line (ใช้ helper เพื่อรองรับ is_deduct_vat)
            for line in rec.line_ids:
                if line.wht_category_id and line.wht_category_id.wht_rate != '0':
                    rate = line.wht_category_id.wht_rate_float
                    line.wht_total = round(
                        line._get_wht_base_amount() * rate / 100.0, 2
                    )
                else:
                    line.wht_total = 0.0

            doc_date = rec.date or fields.Date.today()

            # รวบรวม line ที่เข้าเกณฑ์ (มีหมวดหมู่ + rate + product)
            passed_lines = []
            for line in rec.line_ids:
                if not line.wht_category_id or line.wht_category_id.wht_rate == '0':
                    continue
                if not line.product_id:
                    continue
                passed_lines.append(line)

            # ขั้นตอน 3: สร้าง wht_data ตาม (partner, wht_rate)
            wht_data = {}
            for line in passed_lines:
                wht_cat = line.wht_category_id
                key = (rec.partner_id.id, wht_cat.wht_rate)

                if key not in wht_data:
                    wht_data[key] = {
                        'wht_cat': wht_cat,
                        'base': 0.0,
                    }
                wht_data[key]['base'] += line._get_wht_base_amount()

            partner = rec.partner_id
            if partner.company_type == 'company':
                income_tax_form = 'pnd53'
            else:
                income_tax_form = 'pnd3'

            company = rec.company_id
            account_id = False
            if income_tax_form == 'pnd53':
                account_id = company.account_pnd53_withholding_tax_id.id
            elif income_tax_form == 'pnd3':
                account_id = company.account_pnd3_withholding_tax_id.id
            if not account_id:
                account_id = company.account_withholding_tax_id.id

            # หา cert เดิม จัดกลุ่มตาม (partner, wht_rate ของ line ใบแรก)
            # voucher 1 ใบ มี 1 partner เสมอ; cert มี wt_line[0].wt_percent
            existing_certs_by_key = {}
            for cert in rec.wt_cert_ids.sorted('id'):
                first_line = cert.wt_line[:1]
                if first_line:
                    rate_str = '%g' % first_line.wt_percent
                else:
                    rate_str = '0'
                ckey = (cert.supplier_partner_id.id, rate_str)
                existing_certs_by_key.setdefault(
                    ckey, self.env['withholding.tax.cert']
                )
                existing_certs_by_key[ckey] |= cert

            # cert ที่ key เดิมหายไป -> เอามา recycle
            recyclable_certs = self.env['withholding.tax.cert']
            keys_no_longer = set(existing_certs_by_key.keys()) - set(wht_data.keys())
            for ckey in keys_no_longer:
                recyclable_certs |= existing_certs_by_key[ckey]
            recyclable_certs = recyclable_certs.sorted('id')

            new_keys = [k for k in wht_data.keys() if k not in existing_certs_by_key]
            recycle_map = {}
            recyclable_iter = iter(recyclable_certs)
            for new_key in new_keys:
                cert = next(recyclable_iter, None)
                if cert is None:
                    break
                recycle_map[new_key] = cert
                existing_certs_by_key[new_key] = cert

            # cert ที่ recycle ไม่หมด -> ลบ
            recycled_ids = set(c.id for c in recycle_map.values())
            cert_ids_to_delete = [
                c.id for c in recyclable_certs if c.id not in recycled_ids
            ]
            if cert_ids_to_delete:
                rec._remove_wht_cert_ids(cert_ids_to_delete)

            if not wht_data:
                return True

            new_certs = []
            for key, data in wht_data.items():
                wht_cat = data['wht_cat']
                rate = wht_cat.wht_rate_float
                base = data['base']
                income_desc = wht_cat.income_description or wht_cat.name
                line_vals = {
                    'wt_cert_income_type': '6',
                    'wt_cert_income_desc': income_desc,
                    'base': base,
                    'wt_percent': rate,
                    'amount': base * rate / 100.0,
                }

                if key in existing_certs_by_key:
                    # update cert เดิม - คงเลขรันเดิม
                    existing_cert = existing_certs_by_key[key][0]
                    extra_cert_ids = existing_certs_by_key[key][1:].ids
                    if extra_cert_ids:
                        rec._remove_wht_cert_ids(extra_cert_ids)
                    # set draft ก่อน เพื่อ bypass readonly
                    self.env.cr.execute(
                        "UPDATE withholding_tax_cert SET state = 'draft' WHERE id = %s",
                        (existing_cert.id,)
                    )
                    self.env.cr.execute(
                        "DELETE FROM withholding_tax_cert_line WHERE cert_id = %s",
                        (existing_cert.id,)
                    )
                    self.invalidate_cache()
                    update_vals = {
                        'supplier_partner_id': partner.id,
                        'income_tax_form': income_tax_form,
                        'date': doc_date,
                        'tax_payer': 'withholding',
                        'wt_line': [(0, 0, line_vals)],
                    }
                    if account_id:
                        update_vals['account_id'] = account_id
                    if hasattr(rec, 'branch_id') and rec.branch_id:
                        update_vals['branch_id'] = rec.branch_id.id
                    existing_cert.write(update_vals)
                    self.env.cr.execute(
                        "UPDATE withholding_tax_cert SET state = 'done' WHERE id = %s",
                        (existing_cert.id,)
                    )
                else:
                    # key ใหม่ - ขอเลขรันใหม่
                    seq_ids = self.env['ir.sequence'].search(
                        [('code', '=', 'withholding.tax'),
                         ('company_id', '=', company.id)],
                        order='company_id', limit=1,
                    )
                    if seq_ids:
                        cert_name = seq_ids[0].next_by_id(sequence_date=doc_date)
                    else:
                        cert_name = self.env['ir.sequence'].next_by_code('withholding.tax')

                    cert_vals = {
                        'name': cert_name,
                        'supplier_partner_id': partner.id,
                        'income_tax_form': income_tax_form,
                        'date': doc_date,
                        'tax_payer': 'withholding',
                        'wt_line': [(0, 0, line_vals)],
                    }
                    if account_id:
                        cert_vals['account_id'] = account_id
                    if hasattr(rec, 'branch_id') and rec.branch_id:
                        cert_vals['branch_id'] = rec.branch_id.id
                    new_certs.append((0, 0, cert_vals))

            if new_certs:
                rec.write({'wt_cert_ids': new_certs})
            for cert in rec.wt_cert_ids.filtered(lambda c: c.state == 'draft'):
                self.env.cr.execute(
                    "UPDATE withholding_tax_cert SET state = 'done' WHERE id = %s",
                    (cert.id,)
                )
            rec.invalidate_cache(['wt_cert_ids'])

        return True
