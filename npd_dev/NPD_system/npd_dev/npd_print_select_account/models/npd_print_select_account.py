
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import date
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    document_type = fields.Selection([
        ('invoice', 'ใบแจ้งหนี้'),
        ('tax_invoice', 'ใบกำกับภาษี'),
        ('delivery_note', 'ใบส่งสินค้า'),
    ], string='Document Type', default='invoice')

    # reason_code = fields.Selection([
    #     ('lost_product', 'สินค้าหาย'),
    #     ('befective_goods', 'สินค้าชำรุด'),
    # ], string='Reason Code', default='lost_product')

    # reason_code_id = fields.Many2one(
    #     "scrap.reason.code",
    #     string="ประเภทสินค้า",
    #     states={"posted": [("readonly", True)]},
    #     default=lambda self: self.env['scrap.reason.code'].search([], limit=1)
    # )
    reason_code_id = fields.Many2one(
        "scrap.reason.code",
        string="ประเภทสินค้า",
        # states={"posted": [("readonly", True)]},
        # required=True,
        default=lambda self: self.env['scrap.reason.code'].search([('name', '=', 'ใบแจ้งหนี้ค่าเช่า')], limit=1)
    )

    debt_payment_type = fields.Selection([
        ('rental', 'รับชำระหนี้ค่าเช่า'),
        ('lost', 'รับชำระหนี้ค่าปรับหาย'),
        ('damaged', 'รับชำระหนี้ค่าปรับชำรุด'),
    ], string='ประเภทการรับชำระหนี้', default='', required=False)

    @api.onchange('reason_code_id')
    def _onchange_reason_code_id(self):
        if self.move_type != 'out_refund':
            if self.reason_code_id and self.reason_code_id.name == "สินค้าหาย":
                journal = self.env['account.journal'].search([
                    ('name', '=', 'สมุดรายวันค่าปรับหาย')
                ], limit=1)

                if journal:
                    self.journal_id = journal.id
                else:
                    raise UserError("ไม่พบสมุดรายวัน 'สมุดรายวันค่าปรับหาย' กรุณาตรวจสอบการตั้งค่าในระบบบัญชี")

            elif self.reason_code_id and self.reason_code_id.name == "สินค้าชำรุด":
                journal = self.env['account.journal'].search([
                    ('name', '=', 'สมุดรายวันค่าปรับชำรุด')
                ], limit=1)

                if journal:
                    self.journal_id = journal.id
                else:
                    raise UserError("ไม่พบสมุดรายวัน 'สมุดรายวันค่าปรับชำรุด' กรุณาตรวจสอบการตั้งค่าในระบบบัญชี")

            elif self.reason_code_id and self.reason_code_id.name == "ค่าเช่าส่วนต่าง":
                journal = self.env['account.journal'].search([
                    ('name', '=', 'สมุดรายวันเช่า(สาขา)')
                ], limit=1)

                if journal:
                    self.journal_id = journal.id
                else:
                    raise UserError("ไม่พบสมุดรายวัน 'สมุดรายวันเช่า(สาขา)' กรุณาตรวจสอบการตั้งค่าในระบบบัญชี")

    def action_update_fields(self):
        context = self.env.context
        print(f"Context received: {context}")




        new_move = self.browse(self.id)
        if not new_move:
            print(f"❌ ไม่พบ Invoice ID: {self.id}")
            return True

        print(f"✅ ตรวจพบ Invoice ที่มีอยู่แล้ว: {new_move.name}")

        # ✅ Ensure reason_code_id.name is valid before using accounmid
        if not self.reason_code_id or not self.reason_code_id.name:
            raise UserError("❌ กรุณาเลือกประเภทสินค้าก่อนดำเนินการอัพเดท")



        accounmid = None
        analytic_tag_name = None
        if self.reason_code_id.name == 'ค่าเช่าส่วนต่าง':
            # ✅ ลบรายการเก่า
            new_move.write({'invoice_line_ids': [(5, 0, 0)]})

            # ✅ ดึงสินค้า PR/01363
            product = self.env['product.product'].search([('default_code', '=', 'PR/01363')], limit=1)
            if not product:
                raise UserError("❌ ไม่พบรหัสสินค้า PR/01363 ในระบบ")

            # ✅ ค้นหาบัญชีรายได้
            accounmid_accounmid = self.env['account.account'].search([('code', '=', '4100-01')], limit=1)
            if not accounmid_accounmid:
                raise UserError("❌ ไม่พบบัญชีที่มีรหัส '4100-01' ในระบบ")

            vat_tax = self.env['account.tax'].search([
                ('name', '=', 'ภาษีขายยังไม่ถึงกำหนด Vat 7%')
            ], limit=1)

            # ✅ เพิ่มสินค้าเข้า invoice
            invoice_lines = [(0, 0, {
                'product_id': product.id,
                'name': product.name,
                'quantity': 1.0,
                'price_unit': product.lst_price or 1.0,
                'account_id': accounmid_accounmid.id,
                'tax_ids': [(6, 0, [vat_tax.id])],
            })]

            new_move.write({'invoice_line_ids': invoice_lines})


            new_move._compute_invoice_taxes_by_group()
            new_move._recompute_payment_terms_lines()
            self.update_partner_id()

            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

        else:
            if self.reason_code_id.name == 'สินค้าหาย':
                analytic_tag_name = 'L'
                accounmid = '4100-03'
            elif self.reason_code_id.name == 'สินค้าชำรุด':
                analytic_tag_name = 'D'
                accounmid = '4100-05'
            else:
                raise UserError(f"❌ ประเภทสินค้า '{self.reason_code_id.name}' ไม่ถูกต้อง กรุณาตรวจสอบอีกครั้ง")


            if not accounmid:
                raise UserError("❌ ไม่สามารถกำหนดบัญชีรายได้ เนื่องจาก accounmid ว่างเปล่า")

            accounmid_accounmid = self.env['account.account'].search(
                [('code', '=', accounmid)], limit=1
            )

            if not accounmid_accounmid:
                raise UserError(f"❌ ไม่พบบัญชีที่มีรหัส '{accounmid}' ในระบบ")

            analytic_tag = self.env['account.analytic.tag'].search(
                [('name', '=', analytic_tag_name)], limit=1
            )

            print("self.reason_code_id.name", self.reason_code_id.name)
            print("analytic_tag.id", analytic_tag.id)

            picking_source = self.env['stock.picking'].search(
                [('name', '=', new_move.invoice_origin)], limit=1
            )



            if not picking_source:

                picking_source1 = self.env['stock.picking'].search(
                    [('origin', '=', new_move.invoice_origin)], limit=1
                )
                print(f" พบข้อมูลใน stock_picking สำหรับ Return: {picking_source1.name}")
                # if picking_source1:
                #     picking_source = self.env['stock.picking'].search(
                #         [('origin', '=', f'Return of {picking_source1.name}')], limit=1
                #     )
                if picking_source1:
                    picking_source = self.env['stock.picking'].search([
                        '|', '|',
                        ('origin', '=', f'Return of {picking_source1.name}'),
                        ('origin', '=', f'การส่งคืนของ {picking_source1.name}'),
                        ('origin', '=', f'Returned from {picking_source1.name}')
                    ], limit=1)

                if not picking_source1:
                    # print(f"❌ ไม่พบข้อมูลใน stock.picking สำหรับ Return ของ {new_move.invoice_origin}")
                    raise UserError(f"❌ ไม่พบข้อมูลใน stock picking สำหรับ ค่าของ {new_move.invoice_origin}")
                    # return True

            print(f" พบข้อมูลใน stock_picking สำหรับ Return: {picking_source.id}")

            # ค้นหา stock.scrap
            # รองรับสินค้าชำรุดที่เข้า workflow ส่งซ่อม (npd_scrap_buttons) ซึ่งจะไม่อยู่สถานะ done
            # แต่จะอยู่ที่ pending_repair / under_repair แทน
            # ไม่รวม 'repaired' เพราะซ่อมสำเร็จแล้วจะ reverse คืนสต๊อก สินค้าออกจาก scrap location แล้ว
            scrap_states = ['done', 'pending_repair', 'under_repair']
            stock_scrap_record = self.env['stock.scrap'].search([
                ('picking_id', '=', picking_source.id),
                ('reason_code_id', '=', self.reason_code_id.id),
                ('state', 'in', scrap_states)
            ])

            if not stock_scrap_record:
                raise UserError(
                    "❌ ไม่พบข้อมูลใน รายการแตกหักเสียหาย\n"
                    "⚠️ โปรดตรวจสอบว่า สถานะ เป็น 'เสร็จสิ้น (done)', 'รอดำเนินการแจ้งซ่อม' "
                    "หรือ 'อยู่ระหว่างการซ่อม' หรือไม่\n"
                    f"🔍 รายละเอียดเพิ่มเติม: {self.reason_code_id.name} ยังไม่ถูกสร้าง"
                )

            print(f"✅ พบ {len(stock_scrap_record)} รายการสินค้าใน Scrap ที่ต้องเพิ่มเข้า Invoice")

            #  ลบรายการสินค้าที่มีอยู่ก่อนหน้า โดยใช้ (5,0,0) เพื่อลบทั้งหมด
            new_move.write({'invoice_line_ids': [(5, 0, 0)]})
            print(f"❌ ลบรายการสินค้าที่มีอยู่ก่อนหน้าแล้ว")

            # จัดกลุ่มสินค้าและรวมจำนวน
            product_lines = {}
            for scrap in stock_scrap_record:
                product = scrap.product_id
                if not product:
                    raise UserError("❌ ไม่มีข้อมูลสินค้าใน Scrap Record")

                qty = scrap.scrap_qty
                if product.id in product_lines:
                    product_lines[product.id]['quantity'] += qty
                else:
                    product_lines[product.id] = {
                        'product': product,
                        'quantity': qty,
                    }

            # เตรียมรายการสินค้าที่จะเพิ่มเข้า Invoice
            invoice_lines = []

            for product_data in product_lines.values():
                product = product_data['product']
                quantity = product_data['quantity']

                # คำนวณบัญชีรายได้
                account_id = product.property_account_income_id.id or \
                             new_move.journal_id.default_account_id.id or \
                             new_move.company_id.account_default_id.id

                if not account_id:
                    raise UserError(f"❌ ไม่สามารถกำหนดบัญชีรายได้สำหรับสินค้า {product.name}")

                price = product.lst_price or 1.0

                if self.reason_code_id.name == 'สินค้าหาย':

                    vat_tax = self.env['account.tax'].search([
                        ('name', '=', 'ภาษีขายยังไม่ถึงกำหนด Vat 7%')
                    ], limit=1)

                    # ✅ เพิ่มเงื่อนไขตรวจสอบ
                    if not vat_tax:
                        raise UserError(
                            "❌ ไม่พบเรคคอร์ดภาษีชื่อ 'ภาษีขายยังไม่ถึงกำหนด Vat 7%' กรุณาตรวจสอบการตั้งค่าผังบัญชีภาษี")

                    invoice_lines.append((0, 0, {
                        'product_id': product.id,
                        'name': product.name,
                        'quantity': quantity,
                        'analytic_tag_ids': [(6, 0, [analytic_tag.id])],
                        'price_unit': price,
                        'account_id': accounmid_accounmid.id,
                        'tax_ids': [(6, 0, [vat_tax.id])],
                    }))
                else:
                    invoice_lines.append((0, 0, {
                        'product_id': product.id,
                        'name': product.name,
                        'quantity': quantity,
                        'analytic_tag_ids': [(6, 0, [analytic_tag.id])],
                        'price_unit': price,
                        'account_id': accounmid_accounmid.id,

                    }))

                print(f" เตรียมเพิ่มสินค้า {product.name} จำนวน {quantity} ลงใน Invoice")

            # อัปเดตรายการสินค้าเข้า Invoice
            new_move.with_context(check_move_validity=False).write({
                'invoice_line_ids': invoice_lines
            })

            # 🔥 คำนวณค่าภาษีและบัญชีใหม่
            new_move._compute_invoice_taxes_by_group()
            new_move._recompute_payment_terms_lines()
            self.update_partner_id()
            print(f"✅ Invoice ได้รับการอัปเดตและคำนวณภาษีใหม่แล้ว")
            print(f"⚠️ Invoice นี้จะยังไม่ถูกบันทึกถาวร จนกว่าผู้ใช้จะกดปุ่ม Save ใน Odoo UI")

            #  Force UI Refresh
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def update_partner_id(self):
        if self.partner_shipping_id:
            print(f"🚀 Updating partner_id from {self.partner_id.id} to {self.partner_shipping_id.id}")
            self.write({'partner_id': self.partner_shipping_id.id})
            self.invalidate_cache()  # Force cache refresh
            self.env.cr.commit()  # Ensure the update is saved
            print(f"✅ Updated partner_id: {self.partner_id.id}")
        else:
            print("⚠️ partner_shipping_id is empty. Skipping update.")

        #  Force UI Refresh
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.move_id and self.move_id.move_type == 'out_invoice':

            if self.move_id.reason_code_id and self.move_id.reason_code_id.name == 'ใบแจ้งหนี้ค่าเช่า':
                if self.invoice_origin:
                    raise UserError(f"❌ กรุณาเลือกช่องประเภทสินค้า ตามการแจ้งหนี้ลูกค้า ที่ไม่ใช่ {self.move_id.reason_code_id.name} ")
