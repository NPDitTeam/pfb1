from odoo import models, fields

class StockAPITransferLine(models.Model):
    _name = "stock.api.transfer.line"
    _description = "รายการสินค้าจาก API"

    transfer_id = fields.Many2one("stock.api.transfer", string="เอกสารอ้างอิง", required=True, ondelete="cascade")

    product_name = fields.Char(string="สินค้า", required=True)
    location_api_id = fields.Many2one("stock.api.transfer.location.name", string="คลังต้นทาง (จาก API)",required=True)
    destination_location_id = fields.Many2one(
        "stock.location",
        string="คลังปลายทาง",
        related="transfer_id.location_id",
        store=True,
        readonly=True,
        ondelete='set null'
    )

    location_id = fields.Integer(string="ID คลังจริง (ใช้ตัดสต๊อก)", required=True)  # เก็บ ID เปล่า
    default_code = fields.Char(string="รหัสสินค้า")  # ไม่ต้อง readonly


    available_qty = fields.Float(string="คงเหลือ",required=True)
    request_qty = fields.Float(string="จำนวนขอตัด",required=True)
    status = fields.Char(string="สถานะ", readonly=True, default="รอดำเนินการ")

