# © 2017 Ecosoft (ecosoft.co.th).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    order_sequence = fields.Boolean(string="Order Sequence", readonly=True, index=True)
    quote_id = fields.Many2one(
        comodel_name="sale.order",
        string="Quotation",
        readonly=True,
        ondelete="restrict",
        copy=False,
        help="For Sales Order, this field references to its Quotation",
    )
    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Order",
        readonly=True,
        ondelete="restrict",
        copy=False,
        help="For Quotation, this field references to its Sales Order",
    )
    quotation_state = fields.Selection(
        string="Quotation Status",
        readonly=True,
        related="state",
        help="Only relative quotation states",
    )

    # เพิ่มสถานะใหม่
    # ฟิลด์ใหม่สำหรับสถานะ
    state_sale = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('waiting_to_approve', 'Waiting To Approve'),
            ('approved', 'Approved'),
            ('reject', 'Reject'),
        ],
        string="สถานะการตรวจสอบ",
        default='draft',  # ค่าเริ่มต้น
        readonly=True,  # ล็อกไม่ให้แก้ไข
    )

    approver_id = fields.Many2one('res.users', string="Approver", readonly=True)
    # เพิ่มฟิลด์สำหรับการควบคุมการแสดงปุ่ม Approve
    button_visible = fields.Boolean(
        compute='_compute_button_visible',
        store=False  # ไม่ต้องบันทึกลงฐานข้อมูล
    )

    button_convert_visible_send = fields.Boolean(
        compute='_compute_button_convert_visible_send',
        string='Show Convert Button'
    )

    button_convert_visible = fields.Boolean(
        compute='_compute_button_convert_visible',
        string='Show Convert Button'
    )

    button_visible_reject = fields.Boolean(
        compute='_compute_button_visible_reject',
        string='Show Convert Button'
    )


    # def _compute_button_convert_visible(self):
    #     for rec in self:
    #
    #         if rec.pfb_amount_insurance:
    #             if (rec.pfb_amount > rec.pfb_insurance_min and rec.state == 'draft') or rec.state_sale == 'approved':
    #                 rec.button_convert_visible = True
    #             else:
    #                 rec.button_convert_visible = False
    #         else:
    #             rec.button_convert_visible_send = True

    def _compute_button_convert_visible(self):
        for rec in self:
            # ตั้งค่าเริ่มต้นให้ฟิลด์ button_convert_visible
            rec.button_convert_visible = False  # ค่าเริ่มต้น

            if rec.pfb_amount_insurance:
                # เงื่อนไขที่ต้องการ
                if (rec.pfb_amount > rec.pfb_insurance_min and rec.state == 'draft') or rec.state_sale == 'approved':
                    rec.button_convert_visible = True

                if (rec.pfb_amount == rec.pfb_insurance_min and rec.state == 'draft') or rec.state_sale == 'approved':
                    rec.button_convert_visible = True

            else:
                rec.button_convert_visible = True  # หรือปรับตามความต้องการ


    def _compute_button_convert_visible_send(self):
        for rec in self:
            # เงื่อนไข: แสดงปุ่มเมื่อ approver_id ตรงกับ user ปัจจุบัน

            if rec.pfb_amount_insurance:
                if rec.pfb_amount < rec.pfb_insurance_min and rec.state_sale == 'draft' or  rec.state_sale == 'reject':
                    if rec.pfb_amount <= 0:
                        rec.button_convert_visible_send = False
                    else:
                         rec.button_convert_visible_send = True
                else:
                    rec.button_convert_visible_send = False
            else:
                rec.button_convert_visible_send = False



    def _compute_button_visible(self):
        for rec in self:
            # เงื่อนไข: แสดงปุ่มเมื่อ approver_id ตรงกับ user ปัจจุบัน
            if rec.approver_id.id == self.env.uid and rec.state_sale == 'waiting_to_approve':
                rec.button_visible = True
            else:
                rec.button_visible = False

    def _compute_button_visible_reject(self):
        for rec in self:
            # เงื่อนไข: แสดงปุ่มเมื่อ approver_id ตรงกับ user ปัจจุบัน
            if rec.approver_id.id != '' and rec.state_sale == 'waiting_to_approve':
                rec.button_visible_reject = True
            else:
                rec.button_visible_reject = False


    def action_waiting_to_approve(self):
        """เปิด Popup สำหรับเลือก Approver"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Approver'),
            'res_model': 'sale.order.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            },
        }

    def action_open_approval_popup(self):
        """เปิด popup สำหรับการอนุมัติคำสั่งขาย"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approve Sale Order'),
            'res_model': 'sale.order.approval.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('pfb_npd_all_customs.view_sale_order_approve_wizard_form_v2').id,  # ระบุ view ใหม่
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_note': self.note,
                'default_approver_id': self.approver_id.id,
            },
        }

    def action_approve(self):
        """Logic for Sale Order approval"""
        if not self.approver_id:
            raise UserError(_('No approver selected!'))
        self.write({'state_sale': 'approved'})
        return True

    # def action_approve(self):
    #     if not self.approver_id:
    #         raise UserError(_('No approver selected!'))
    #     self.write({'state_sale': 'approved'})

    def action_reject(self):
        if not self.approver_id:
            raise UserError(_('No reject selected!'))
        self.write({'state_sale': 'reject'})

        # ฟังก์ชันตรวจสอบเงื่อนไขการแสดงปุ่ม

    @api.model
    def create(self, vals):
        order_sequence = vals.get("order_sequence") or self.env.context.get(
            "order_sequence"
        )
        if not order_sequence and vals.get("name", "/") == "/":
            vals["name"] = self.env["ir.sequence"].next_by_code("sale.quotation") or "/"
        return super().create(vals)

    def _prepare_order_from_quotation(self):
        return {
            "name": self.env["ir.sequence"].next_by_code("sale.order") or "/",
            "order_sequence": True,
            "quote_id": self.id,
            "client_order_ref": self.client_order_ref,
        }

    def action_convert_to_order(self):
        self.ensure_one()
        if self.order_sequence:
            raise UserError(_("Only quotation can convert to order"))
        order = self.copy(self._prepare_order_from_quotation())
        self.order_id = order.id  # Reference from this quotation to order
        if self.state == "draft":
            self.action_done()
        return self.open_duplicated_sale_order()

    @api.model
    def open_duplicated_sale_order(self):
        return {
            "name": _("Sales Order"),
            "view_mode": "form",
            "view_id": False,
            "res_model": "sale.order",
            "context": {"default_order_sequence": True, "order_sequence": True},
            "type": "ir.actions.act_window",
            "nodestroy": True,
            "target": "current",
            "domain": "[('order_sequence', '=', True)]",
            "res_id": self.order_id and self.order_id.id or False,
        }
