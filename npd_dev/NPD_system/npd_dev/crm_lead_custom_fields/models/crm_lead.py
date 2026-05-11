from odoo import models, fields, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # เพิ่มฟิลด์หน้างาน
    x_job_position = fields.Text(
        string='หน้างาน',
        help='ตำแหน่งหน้างาน'
    )

    # เพิ่มฟิลด์สินค้าที่สนใจ
    x_products_interest = fields.Text(
        string='สินค้าที่สนใจ',
        help='รายการสินค้าหรือบริการที่ลูกค้าสนใจ'
    )

    # เพิ่มฟิลด์รายละเอียดโครงการ
    x_project_details = fields.Text(
        string='รายละเอียดโครงการ',
        help='รายละเอียดของโครงการที่ลูกค้าต้องการ'
    )

    # เพิ่มฟิลด์ระยะเวลาโครงการ
    x_project_duration = fields.Char(
        string='ระยะเวลาโครงการ',
        help='ระยะเวลาในการดำเนินโครงการ เช่น 3 เดือน, 6 เดือน'
    )

    # เพิ่มฟิลด์งบประมาณโครงการ
    x_project_budget = fields.Float(
        string='งบประมาณโครงการ',
        help='งบประมาณสำหรับโครงการ (บาท)',
        digits='Product Price'
    )