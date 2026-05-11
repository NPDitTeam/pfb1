# -*- coding: utf-8 -*-

from odoo import models, fields


class CommissionDetailWizardLine(models.TransientModel):
    _name = 'commission.detail.wizard.line'
    _description = 'รายละเอียดค่าคอมมิชชั่นแต่ละ DB'

    wizard_id = fields.Many2one('commission.detail.wizard', string='Wizard', ondelete='cascade')
    db_name = fields.Char(string='Database')
    status = fields.Char(string='สถานะ')
    match_count = fields.Integer(string='จำนวนที่ Match')
    net_rental = fields.Float(string='Net Rental', digits=(16, 2))


class CommissionDetailWizardSalesLine(models.TransientModel):
    _name = 'commission.detail.wizard.sales.line'
    _description = 'รายละเอียดยอด Sales ที่ดึงจาก API (กรองตามสาขา)'

    wizard_id = fields.Many2one('commission.detail.wizard', string='Wizard', ondelete='cascade')
    db_name = fields.Char(string='Database')
    sales_contact_name = fields.Char(string='Sales ที่ติดต่อ')
    branch_name = fields.Char(string='สาขา')
    rental_amount = fields.Float(string='ยอดเช่า', digits=(16, 2))
    payment_received = fields.Float(string='รับชำระหนี้', digits=(16, 2))
    outstanding_debt = fields.Float(string='หนี้ค้างชำระ', digits=(16, 2))
    shipping_cost = fields.Float(string='ค่าขนส่ง', digits=(16, 2))
    net_rental = fields.Float(string='ยอดเช่าสุทธิ', digits=(16, 2))


class CommissionDetailWizard(models.TransientModel):
    _name = 'commission.detail.wizard'
    _description = 'รายละเอียดการดึงค่าคอมมิชชั่น'

    commission_type = fields.Selection([
        ('branch', 'ค่าคอมมิชชั่นสาขา'),
        ('sale', 'ค่าคอมมิชชั่นSale'),
    ], string='ประเภท', readonly=True)
    employee_name = fields.Char(string='พนักงาน', readonly=True)
    branch_name = fields.Char(string='สาขา', readonly=True)
    month = fields.Integer(string='เดือน', readonly=True)
    year = fields.Char(string='ปี', readonly=True)
    detail_line_ids = fields.One2many(
        'commission.detail.wizard.line', 'wizard_id',
        string='รายละเอียดแต่ละ DB')
    # ===== Sales detail lines (แสดงในรายละเอียดค่าคอมสาขา) =====
    sales_line_ids = fields.One2many(
        'commission.detail.wizard.sales.line', 'wizard_id',
        string='รายละเอียดยอด Sales (กรองตามสาขา)')
    sales_total_net_rental = fields.Float(string='รวมยอด Sales สุทธิ', digits=(16, 2), readonly=True)
    grand_total_net_rental = fields.Float(string='รวมยอดสุทธิทั้งหมด (สาขา + Sales)', digits=(16, 2), readonly=True)

    total_amount = fields.Float(string='รวม Net Rental ทั้งหมด', digits=(16, 2), readonly=True)
    # ===== อัตราค่าคอมสาขา/Sales (จากตั้งค่า) =====
    branch_comm_rate = fields.Float(string='อัตราค่าคอมสาขา (%)', digits=(16, 2), readonly=True)
    sales_comm_rate = fields.Float(string='อัตราค่าคอม Sales (%)', digits=(16, 2), readonly=True)
    branch_after_rate = fields.Float(string='Net Rental สาขา × อัตรา', digits=(16, 2), readonly=True)
    sales_after_rate = fields.Float(string='Net Rental Sales × อัตรา', digits=(16, 2), readonly=True)
    active_emp_count = fields.Integer(string='จำนวนพนักงาน Active ในสาขา', readonly=True)
    per_person_amount = fields.Float(string='ค่าคอมต่อคน', digits=(16, 2), readonly=True)
    commission_rate = fields.Float(string='อัตราคอมมิชชั่น (%)', digits=(16, 2), readonly=True)
    commission_result = fields.Float(string='ค่าคอมมิชชั่นที่ได้', digits=(16, 2), readonly=True)
    my_ratio = fields.Float(string='สัดส่วนตัวเอง', digits=(16, 2), readonly=True)
    total_ratio = fields.Float(string='สัดส่วนรวมทั้งสาขา', digits=(16, 2), readonly=True)
