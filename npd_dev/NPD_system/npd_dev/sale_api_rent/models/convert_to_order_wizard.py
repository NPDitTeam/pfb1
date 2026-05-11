# from odoo import models, fields, api
#
# class ConvertToOrderWizard(models.TransientModel):
#     _name = 'convert.to.order.wizard'
#     _description = 'Wizard to Convert to Order'
#
#     database_selection = fields.Selection([
#         ('test_2025_import002', 'test_2025_import002'),
#         ('test_2025_import003', 'test_2025_import003')
#     ], string="Select Database", required=True)
#
#     so_number = fields.Char(string="SO Number", required=True)
#
#     def action_confirm(self):
#         """ ทำงานเมื่อกดปุ่มยืนยัน """
#         active_id = self.env.context.get('active_id')
#         sale_order = self.env['sale.order'].browse(active_id)
#
#         if sale_order:
#             # อัพเดตเลขที่ SO
#             sale_order.write({
#                 'name': self.so_number
#             })
#
#         return {'type': 'ir.actions.act_window_close'}
