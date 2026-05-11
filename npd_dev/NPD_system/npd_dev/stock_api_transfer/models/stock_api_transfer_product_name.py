from odoo import models, fields
import requests
import logging

_logger = logging.getLogger(__name__)


class StockAPITransferProductName(models.Model):
    _name = 'stock.api.transfer.product.name'
    _description = 'ชื่อสินค้าจาก API'

    name = fields.Char(string='ชื่อสินค้า', required=True)

    @staticmethod
    def get_api_stock(db_name):
        """เรียก API เพื่อดึงข้อมูลสต๊อกจากฐานข้อมูลที่เลือก"""
        print("db_name**************",db_name)
        username = "Npd_admin"
        password = "1234"

        try:
            login_url = "http://localhost:8077/web/session/authenticate"
            # login_url = "https://npderp.com/web/session/authenticate"
            login_payload = {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "db": db_name,
                    "login": username,
                    "password": password
                },
                "id": 1
            }

            session = requests.Session()
            login_response = session.post(login_url, json=login_payload)
            login_response.raise_for_status()

            session_id = login_response.cookies.get("session_id")
            if not session_id:
                raise ValueError("ไม่สามารถเข้าสู่ระบบ (ไม่มี session_id)")

            stock_url = "http://localhost:8077/api/get_stock"
            # stock_url = "https://npderp.com/api/get_stock"
            stock_payload = {
                "db": db_name,
                "username": username,
                "password": password
            }
            headers = {
                "Content-Type": "application/json",
                "Cookie": f"session_id={session_id}"
            }

            stock_response = session.post(stock_url, json=stock_payload, headers=headers)
            stock_response.raise_for_status()
            stock_data = stock_response.json()

            # ตรวจสอบว่า response มี structure ที่ถูกต้อง
            if not isinstance(stock_data.get("result", {}).get("result", []), list):
                raise ValueError("รูปแบบข้อมูล API ผิดพลาด: result.result ต้องเป็น list")

            return stock_data.get("result", {}).get("result", [])

        except Exception as e:
            _logger.error("❌ ERROR ดึงข้อมูลจาก API ใน get_api_stock(): %s", str(e))
            return []
