from odoo import models, fields, api
import pytz
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class BaseModelTimezone(models.AbstractModel):
    _inherit = "base"

    def _convert_datetime_to_tz(self, dt_value):
        """ ฟังก์ชันกลางใช้แปลงเวลาจาก UTC → Asia/Bangkok """
        tz = pytz.timezone('Asia/Bangkok')
        if isinstance(dt_value, str):
            dt_value = fields.Datetime.from_string(dt_value)
        if dt_value.tzinfo is None:
            dt_value = pytz.utc.localize(dt_value)
        return dt_value.astimezone(tz)

    @api.model
    def create(self, vals):
        for field_name in vals:
            field = self._fields.get(field_name)
            if field and field.type == "datetime" and isinstance(vals[field_name], (str, datetime)):
                converted_time = self._convert_datetime_to_tz(vals[field_name])
                vals[field_name] = converted_time.strftime('%Y-%m-%d %H:%M:%S')

                # 🔹 Log และ Debug
                _logger.info(f"[CREATE] {field_name} | UTC: {vals[field_name]} | Asia/Bangkok: {converted_time}")

        return super(BaseModelTimezone, self).create(vals)

    def write(self, vals):
        for field_name in vals:
            field = self._fields.get(field_name)
            if field and field.type == "datetime" and isinstance(vals[field_name], (str, datetime)):
                converted_time = self._convert_datetime_to_tz(vals[field_name])
                vals[field_name] = converted_time.strftime('%Y-%m-%d %H:%M:%S')

                # 🔹 Log และ Debug
                _logger.info(f"[WRITE] {field_name} | UTC: {vals[field_name]} | Asia/Bangkok: {converted_time}")

        return super(BaseModelTimezone, self).write(vals)

    def read(self, fields=None, load='_classic_read'):
        result = super(BaseModelTimezone, self).read(fields, load)
        for record in result:
            for field_name, value in record.items():
                field = self._fields.get(field_name)

                # ✅ ป้องกันกรณีที่ field เป็น list (one2many/many2many)
                if isinstance(value, list):
                    continue  # ข้าม field ที่เป็น list ไปเลย

                # ✅ ตรวจสอบว่าเป็น fields.Datetime และไม่ใช่ list
                if field and field.type == "datetime" and isinstance(value, (str, datetime)):
                    converted_time = self._convert_datetime_to_tz(value).strftime('%Y-%m-%d %H:%M:%S')
                    record[field_name] = converted_time

                    # 🔹 Log และ Debug
                    _logger.info(f"[READ] {field_name} | Converted Asia/Bangkok: {record[field_name]}")

        return result
