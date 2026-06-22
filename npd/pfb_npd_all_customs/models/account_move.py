from itertools import chain

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
import logging
_logger = logging.getLogger(__name__)

# class SaleAdvancePaymentInv(models.TransientModel):
#     _inherit = "sale.advance.payment.inv"
#
#
#     def _prepare_invoice_values(self, order, name, amount, so_line):
#         print('_prepare_invoice_values',order.pfb_so_type)
#
#         if order.pfb_so_type == 'rent':
#             invoice_vals = {
#                 'ref': order.client_order_ref,
#                 'move_type': 'out_invoice',
#                 'invoice_origin': order.name,
#                 'invoice_user_id': order.user_id.id,
#                 'narration': order.note,
#                 'partner_id': order.partner_invoice_id.id,
#                 'fiscal_position_id': (order.fiscal_position_id or order.fiscal_position_id.get_fiscal_position(order.partner_id.id)).id,
#                 'partner_shipping_id': order.partner_shipping_id.id,
#                 'currency_id': order.pricelist_id.currency_id.id,
#                 'payment_reference': order.reference,
#                 'invoice_payment_term_id': order.payment_term_id.id,
#                 'partner_bank_id': order.company_id.partner_id.bank_ids[:1].id,
#                 'team_id': order.team_id.id,
#                 'campaign_id': order.campaign_id.id,
#                 'medium_id': order.medium_id.id,
#                 'source_id': order.source_id.id,
#                 'pfb_so_type': order.pfb_so_type,
#                 'pfb_date_of_rent': order.pfb_date_of_rent,
#                 'pfb_objective_id': order.pfb_objective_id.id,
#                 'pfb_amount_insurance': order.pfb_amount_insurance,
#                 'pfb_dis_amount_insurance': order.pfb_dis_amount_insurance,
#                 'pfb_amount': order.pfb_amount,
#                 'invoice_line_ids': [(0, 0, {
#                     'name': name,
#                     'price_unit': amount,
#                     'quantity': 1.0,
#                     'product_id': self.product_id.id,
#                     'product_uom_id': so_line.product_uom.id,
#                     'tax_ids': [(6, 0, so_line.tax_id.ids)],
#                     'sale_line_ids': [(6, 0, [so_line.id])],
#                     'analytic_tag_ids': [(6, 0, so_line.analytic_tag_ids.ids)],
#                     'analytic_account_id': order.analytic_account_id.id or False,
#                     'pfb_so_rent_ok': so_line.pfb_so_rent_ok,
#                     'pfb_quantity': so_line.pfb_quantity,
#                     'pfb_insurance_price': so_line.pfb_insurance_price,
#                     'pfb_objective_id': so_line.pfb_objective_id.id,
#                 })],
#             }
#             return invoice_vals
#         else:
#             return super()._prepare_invoice_values(order, name, amount, so_line)




class AccountMove(models.Model):
    _inherit = 'account.move'

    # def _compute_amount_insurance(self):
    #     for order in self:
    #         total = 0.0
    #         for line in order.order_line:
    #             total += (line.pfb_quantity*line.pfb_insurance_price)
    #             print('total',total)
    #
    #         order.pfb_amount_insurance = total
    #         order.pfb_amount = total - order.pfb_dis_amount_insurance

    pfb_so_type = fields.Selection([
        ('sale', 'Sales'),
        ('rent', 'Rent')],
        string="Sale Type",
        index=True, default='sale', required=True)

    pfb_date_of_rent = fields.Integer(string="Day of Rent",)
    pfb_objective_id = fields.Many2one('sale.objective', string="Objective")
    pfb_amount_insurance = fields.Float('ค่าประกันสินค้า',digits=0)
    pfb_dis_amount_insurance = fields.Float('ส่วนลดประกันสินค้า',digits=0)
    pfb_amount = fields.Float('ค่าประกันสุทธิ', digits=0)

    # def create(self, values):
    #     print('context--->',self._context)
    #     print('values--->',values)
    #     raise UserError(self.context)
    #     res = super().create(values)
    #     print('res', res)
    #     res.picking_id.write({
    #         'picking_transport_id': res.transport_info_id.id,
    #     })
    #     return res

    total_rental_discount = fields.Float(
        string="- Rental Discount",
        compute="_compute_total_rental_discount",
        store=True
    )

    npd_return_rent_discount_pulled = fields.Float(
        string="ส่วนลดค่าเช่าจากใบคืน (ดึงแล้ว)",
        copy=False,
        help="ยอดส่วนลดค่าเช่า (rent_discount) จากใบคืนที่ถูกเพิ่มเป็นบรรทัดในใบลดหนี้นี้แล้ว "
             "— ใช้กันการดึงซ้ำเมื่อกดปุ่มหลายครั้ง",
    )

    @api.depends("invoice_line_ids.discount_type_selection", "invoice_line_ids.discount_amount","discount_amt_line","amount_total","amount_residual")
    def _compute_total_rental_discount(self):
        for move in self:
            # รวมค่า discount_amount จาก account.move.line ที่มี discount_type_selection = 'rental'
            move.total_rental_discount = sum(
                (line.discount_amount or 0.0) for line in move.invoice_line_ids if
                line.discount_type_selection == 'rental'
            )

            # รวมค่า discount_amount ที่ไม่มี discount_type_selection หรือเป็น 'product'
            move.discount_amt_line = sum(
                (line.discount_amount or 0.0) for line in move.invoice_line_ids if
                not line.discount_type_selection or line.discount_type_selection == 'product'
            )

            # เช็คเงื่อนไขทั้งสองอย่าง: ต้องมี total_rental_discount และมี discount_type_selection เป็น 'product'
            if move.discount_amt_line:

                move.amount_residual = move.amount_total

            # Debugging output (สามารถเอาออกได้ถ้าไม่ต้องการ)
            # print("🚀 Updated total_rental_discount:", move.total_rental_discount)
            # print("🚀 Updated discount_amt_line:", move.discount_amt_line)

    # ===================================================================
    # ดึงส่วนลดค่าเช่า (rent_discount) จากใบคืน เข้าใบลดหนี้
    # -------------------------------------------------------------------
    # ปัญหา: ส่วนลดค่าเช่าที่ให้ลูกค้าเพิ่มตอนคืนของ ถูกเก็บไว้ที่
    #        stock.picking.rent_discount (อนุมัติผ่าน wizard) และแสดงบน
    #        "ใบคืนการเช่า" เท่านั้น ไม่เคยไหลเข้าใบลดหนี้ → ใบลดหนี้จึง
    #        "ขาดยอด" เท่ากับ rent_discount (เช่น 76.30)
    #
    # วิธีแก้: ปุ่มนี้จะรวม rent_discount ของใบคืนที่ "อนุมัติแล้ว" ซึ่งผูกกับ
    #         Sales Order เดียวกัน แล้วบวกเข้า target_amount_total ของใบลดหนี้
    #         (target_amount_total เป็นกลไกของ npd_rent_price_round ที่บังคับ
    #         ยอดรวม incl-VAT ให้เป๊ะตามที่กำหนด — ใช้แทนการใส่ discount_amount
    #         รายบรรทัด ซึ่งจะถูก Method A คำนวณทับทิ้งทุกครั้งที่ save/post)
    # ===================================================================
    def _get_related_return_pickings(self):
        """หาใบคืน (stock.picking) ที่อนุมัติแล้ว + มี rent_discount > 0
        ซึ่งผูกกับ Sales Order เดียวกับใบลดหนี้นี้"""
        self.ensure_one()
        moves = self | self.reversed_entry_id
        orders = moves.invoice_line_ids.sale_line_ids.order_id
        # fallback: จับคู่จาก invoice_origin (ชื่อ SO) เผื่อใบลดหนี้ไม่ได้ link
        # sale_line_ids โดยตรง
        origin_names = set()
        for m in moves:
            if m.invoice_origin:
                origin_names |= {
                    n.strip() for n in m.invoice_origin.split(',') if n.strip()
                }
        if origin_names:
            orders |= self.env['sale.order'].search(
                [('name', 'in', list(origin_names))])
        if not orders:
            return self.env['stock.picking']
        return self.env['stock.picking'].search([
            ('sale_id', 'in', orders.ids),
            ('approval_state', '=', 'approved'),
            ('rent_discount', '>', 0),
        ])

    def action_pull_return_rent_discount(self):
        """ปุ่ม: ดึงส่วนลดค่าเช่าจากใบคืน → เพิ่มเป็น "บรรทัดจริง" ในใบลดหนี้

        เหตุที่ใช้บรรทัดจริง ไม่ใช่ target_amount_total:
        amount_total เป็น stored-compute (bi_sale_purchase_discount_with_tax)
        ที่ recompute ใหม่ตอน post → ยอดที่บังคับผ่าน target/SQL จะถูกทับกลับ
        เป็นยอดธรรมชาติ การเพิ่มเป็นบรรทัดจริงทำให้ยอดมาจากการคำนวณปกติ จึง
        "รอด" การ post และ recompute ทุกครั้ง อีกทั้งได้ฐาน/VAT แยกถูกต้อง
        (Method A: price_unit incl-VAT → subtotal = price_unit/1.07 × qty)
        """
        self.ensure_one()
        if self.move_type != 'out_refund':
            raise UserError(_("ฟังก์ชันนี้ใช้ได้เฉพาะใบลดหนี้ (Credit Note) เท่านั้น"))
        if self.state != 'draft':
            raise UserError(_("ดึงส่วนลดค่าเช่าได้เฉพาะตอนใบลดหนี้เป็นฉบับร่างเท่านั้น"))

        pickings = self._get_related_return_pickings()
        desired = round(sum(pickings.mapped('rent_discount')), 2)
        if not desired:
            raise UserError(_(
                "ไม่พบส่วนลดค่าเช่า (rent_discount) ที่อนุมัติแล้วในใบคืนที่เกี่ยวข้อง\n"
                "ตรวจสอบว่าใบคืนถูกอนุมัติ (approval_state = approved) "
                "และกรอกส่วนลดค่าเช่าไว้แล้ว"))

        names = ', '.join(pickings.mapped('name')) or '-'
        line_name = _("ส่วนลดค่าเช่าเพิ่มตามใบคืน %s") % names

        # idempotent: ถ้ามีบรรทัดส่วนลดจากใบคืนอยู่แล้ว → อัปเดตยอด, ไม่งั้นสร้างใหม่
        disc_line = self.invoice_line_ids.filtered('npd_is_return_rent_discount')[:1]
        if disc_line:
            disc_line.write({
                'name': line_name,
                'quantity': 1,
                'price_unit': desired,
            })
        else:
            # คัดลอกบัญชี/ภาษี/วิเคราะห์ จากบรรทัดค่าเช่าที่มีอยู่ เพื่อให้ลงบัญชี
            # + แยก VAT ตรงกับบรรทัดอื่น (tax 7% include → price_unit คิดเป็น incl-VAT)
            template = self.invoice_line_ids.filtered(
                lambda l: l.account_id and not l.exclude_from_invoice_tab)[:1]
            if not template:
                raise UserError(_(
                    "ไม่พบบรรทัดสินค้าในใบลดหนี้เพื่อใช้เป็นต้นแบบบัญชี/ภาษี"))
            vals = {
                'name': line_name,
                'quantity': 1,
                'price_unit': desired,
                'account_id': template.account_id.id,
                'tax_ids': [(6, 0, template.tax_ids.ids)],
                'discount_type_selection': 'rental',
                'npd_is_return_rent_discount': True,
            }
            if template.analytic_account_id:
                vals['analytic_account_id'] = template.analytic_account_id.id
            if template.analytic_tag_ids:
                vals['analytic_tag_ids'] = [(6, 0, template.analytic_tag_ids.ids)]
            self.write({'invoice_line_ids': [(0, 0, vals)]})

        # ล้าง target_amount_total เดิม (วิธีที่ไม่รอด post) เพื่อไม่ให้ตีกับยอดบรรทัด
        if self.target_amount_total:
            self.target_amount_total = 0.0

        self.npd_return_rent_discount_pulled = desired
        self.message_post(body=_(
            "ดึงส่วนลดค่าเช่าจากใบคืน %s รวม %.2f บาท "
            "→ เพิ่มเป็นบรรทัดส่วนลดค่าเช่าในใบลดหนี้ (ยอดรวมเพิ่มขึ้น %.2f บาท)"
        ) % (names, desired, desired))
        return True


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    pfb_so_rent_ok = fields.Boolean('Can be Rent')
    move_type_parent = fields.Selection(related='move_id.move_type', store=True)
    move_state_parent = fields.Selection(related='move_id.state', store=True)
    # pfb_date_of_rent = fields.Integer(string="Day of Rent")
    # pfb_date_of_rent = fields.Integer(related='sale_line_ids.pfb_date_of_rent')
    pfb_date_of_rent = fields.Integer(string="Day of Rent", store=True)
    pfb_quantity = fields.Integer(string="Quantity Rent", store=True)
    pfb_insurance_price = fields.Float(string="Insurance")
    pfb_objective_id = fields.Many2one('sale.objective', string="Objective")
    discount_type_selection = fields.Selection(
        [
            ('product', 'ส่วนลดสินค้า'),
            ('rental', 'ส่วนลดค่าเช่า')
        ],
        string="ประเภทส่วนลด",
        default='product'
    )
    # ทำเครื่องหมายบรรทัดที่ปุ่ม "ดึงส่วนลดค่าเช่าจากใบคืน" สร้างขึ้น
    # ใช้กันสร้างซ้ำ + อัปเดตยอดเมื่อกดดึงใหม่
    npd_is_return_rent_discount = fields.Boolean(
        string="บรรทัดส่วนลดค่าเช่าจากใบคืน",
        copy=False,
    )

    @api.onchange('pfb_date_of_rent', 'pfb_quantity')
    def _onchange_pfb_date_of_rent(self):
        if self.move_id:
            move_id_int = self.move_id.id
            _logger.warning(f"📌 ตรวจสอบ move_id: {move_id_int}")

            related_lines = self.env['account.move.line'].search([('move_id', '=', move_id_int)])
            _logger.warning(f"🔎 พบ account.move.line {len(related_lines)} รายการ ใน move_id {move_id_int}")

            for line in related_lines:
                _logger.warning(
                    f"📌 LINE ID: {line.id} | Product: {line.product_id.display_name} | "
                    f"pfb_date_of_rent: {line.pfb_date_of_rent} | pfb_quantity: {line.pfb_quantity}"
                )

            # ✅ UPDATE ทั้งสองฟิลด์
            if self._origin and self._origin.id:
                self.env.cr.execute("""
                        UPDATE account_move_line
                        SET pfb_date_of_rent = %s,
                            pfb_quantity = %s
                        WHERE id = %s
                    """, (
                    self.pfb_date_of_rent or 0,
                    self.pfb_quantity or 0,
                    self._origin.id
                ))
                _logger.warning(
                    f"✅ อัปเดต pfb_date_of_rent = {self.pfb_date_of_rent}, "
                    f"pfb_quantity = {self.pfb_quantity} สำเร็จสำหรับ ID {self._origin.id}"
                )
            else:
                _logger.warning("⚠️ ยังไม่มี ID ที่แท้จริง (self._origin.id)")
        else:
            _logger.warning("❌ ยังไม่มีค่า move_id")