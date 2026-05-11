from odoo import models, fields


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def search_lost_leads(self):
        # สร้าง domain สำหรับค้นหา leads ที่เป็น "Lost"
        domain = [
            ('probability', '=', 0),  # ความน่าจะเป็นเท่ากับ 0
            ('active', '=', False),  # ไม่ active
            ('type', 'in', ['lead', 'opportunity']),  # เป็น lead หรือ opportunity
            ('filter_lost_won', '=', 'lost')  # กรองเฉพาะ "Lost"
        ]

        # ใช้ domain เพื่อค้นหา leads ที่ตรงกับเงื่อนไข
        lost_leads = self.search(domain)

        # สามารถทำอะไรกับ leads ที่ค้นหาได้ต่อจากนี้ เช่น นับจำนวน leads ที่พบ
        lost_leads_count = len(lost_leads)

        return lost_leads_count
