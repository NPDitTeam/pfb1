# -*- coding: utf-8 -*-
from odoo import models, api, fields


class PayrollHoliday(models.Model):
    """
    Inherit payroll.holiday เพื่อเพิ่ม API method สำหรับ JSON-RPC
    """
    _inherit = 'payroll.holiday'

    @api.model
    def get_company_holidays(self, year=None):
        """
        JSON-RPC method: คืนค่ารายการวันหยุดของปีที่ระบุ
        เรียกผ่าน: /web/dataset/call_kw
            model: payroll.holiday
            method: get_company_holidays
            args: []
            kwargs: {'year': 2026}  # optional, default = ปีปัจจุบัน

        Return: [{'date': 'YYYY-MM-DD', 'name': '...'}, ...]
        """
        target_year = year or fields.Date.today().year
        template = self.search([('year', '=', int(target_year))], limit=1)
        if not template:
            return []
        return [
            {
                'id': line.id,
                'date': fields.Date.to_string(line.date) if line.date else '',
                'name': line.name or '',
            }
            for line in template.line_ids.sorted(key=lambda l: l.date or fields.Date.today())
        ]

    @api.model
    def get_long_holiday_ranges(self, year=None, min_days=2):
        """
        คืนเฉพาะช่วงวันหยุดที่ติดกัน >= min_days วัน
        Return: [[{'date': ..., 'name': ...}, ...], [...]]
        """
        holidays = self.get_company_holidays(year=year)
        if not holidays:
            return []

        # สร้าง dict {date_str: item}
        items = sorted(holidays, key=lambda x: x['date'])
        ranges = []
        current = [items[0]]
        for i in range(1, len(items)):
            prev_date = fields.Date.from_string(items[i - 1]['date'])
            curr_date = fields.Date.from_string(items[i]['date'])
            if (curr_date - prev_date).days == 1:
                current.append(items[i])
            else:
                if len(current) >= min_days:
                    ranges.append(current)
                current = [items[i]]
        if len(current) >= min_days:
            ranges.append(current)
        return ranges
