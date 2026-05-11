from odoo import http
from odoo.http import request

class RealTimeDebtorController(http.Controller):

    @http.route('/baankheaw/realtime_debtors', auth='user', website=True)
    def render_realtime_debtors(self, **kwargs):
        # 🔄 ดึงข้อมูลแบบรีลไทม์มาเก็บไว้ที่ Model
        request.env['baankheaw.debtor_summary'].sudo().fetch_and_store_realtime_data()

        # 📦 อ่านข้อมูลจาก Odoo ORM เพื่อแสดงผล
        records = request.env['baankheaw.debtor_summary'].sudo().search([])

        return request.render('baankheaw.realtime_debtor_template', {
            'records': records
        })
