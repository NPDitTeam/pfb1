from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """Override search to apply branch filter conditionally"""
        user = self.env.user
        user_branch = user.branch_id
        
        # ตรวจสอบว่าพนักงานอยู่แผนก Sales หรือไม่
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        is_sales_department = employee and employee.department_id and employee.department_id.name == 'Sales'
        
        if is_sales_department:
            if user.sales_view_all_invoice:
                # ถ้าติ๊กเปิด "Sales เห็นใบแจ้งหนี้ทั้งหมด": แสดงใบแจ้งหนี้ทุกสาขาทั้งหมด ไม่กรอง
                pass
            else:
                # ถ้าอยู่แผนก Sales: แสดงใบแจ้งหนี้ทุกสาขา แต่เฉพาะที่ตัวเองเป็น Sales ที่ติดต่อ (sales_contact_id)
                sales_domain = [
                    ('sales_contact_id', '=', user.id)
                ]
                if args:
                    args = sales_domain + args
                else:
                    args = sales_domain
        elif not user.bypass_branch_filter and user_branch:
            # ถ้าไม่ใช่แผนก Sales และไม่ได้ติ๊กถูก bypass: ใช้เงื่อนไขกรอง branch เดิม
            branch_domain = ['|', ('branch_id', '=', False),
                             ('branch_id', '=', user_branch.id)]
            if args:
                args = branch_domain + args
            else:
                args = branch_domain

        return super(AccountMove, self).search(args, offset=offset, limit=limit, order=order, count=count)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """Override search to apply branch filter conditionally"""
        user = self.env.user
        user_branch = user.branch_id
        
        # ตรวจสอบว่าพนักงานอยู่แผนก Sales หรือไม่
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        is_sales_department = employee and employee.department_id and employee.department_id.name == 'Sales'
        
        if is_sales_department:
            if user.sales_view_all_payment:
                # ถ้าติ๊กเปิด "Sales เห็นใบรับชำระทั้งหมด": แสดงใบรับชำระทุกสาขาทั้งหมด ไม่กรอง
                pass
            else:
                # ถ้าอยู่แผนก Sales: แสดงใบรับชำระทุกสาขา แต่เฉพาะที่เกี่ยวข้องกับตัวเอง
                # กรองจาก invoice ที่มี sales_contact_id (Sales ที่ติดต่อ) เป็นชื่อตัวเอง
                my_invoice_ids = self.env['account.move'].sudo().search([
                    ('sales_contact_id', '=', user.id)
                ]).ids
                my_payment_ids = self.env['account.payment.invoice'].sudo().search([
                    ('invoice_id', 'in', my_invoice_ids)
                ]).mapped('payment_id').ids
                sales_domain = [
                    ('id', 'in', my_payment_ids)
                ]
                if args:
                    args = sales_domain + args
                else:
                    args = sales_domain
        elif not user.bypass_branch_filter_payment and user_branch:
            # ถ้าไม่ใช่แผนก Sales และไม่ได้ติ๊กถูก bypass: ใช้เงื่อนไขกรอง branch เดิม
            branch_domain = ['|', ('branch_id', '=', False),
                             ('branch_id', '=', user_branch.id)]
            if args:
                args = branch_domain + args
            else:
                args = branch_domain

        return super(AccountPayment, self).search(args, offset=offset, limit=limit, order=order, count=count)
