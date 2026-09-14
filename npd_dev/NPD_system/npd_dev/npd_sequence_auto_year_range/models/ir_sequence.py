# -*- coding: utf-8 -*-

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

import pytz

from odoo import api, models

from .sub_sequence_format import describe, detect_period, infer_format, render, year_periods

_logger = logging.getLogger(__name__)

# server เป็น UTC แต่ "ขึ้นปีใหม่" ต้องนับตามเวลาไทย
COMPANY_TZ = 'Asia/Bangkok'


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    @api.model
    def _npd_today(self, now_utc=None):
        """วันที่ปัจจุบันตามเวลาไทย (now_utc = datetime แบบ UTC ไม่มี tzinfo ใช้ทดสอบ)"""
        now_utc = now_utc or datetime.utcnow()
        return pytz.utc.localize(now_utc).astimezone(pytz.timezone(COMPANY_TZ)).date()

    @api.model
    def _cron_npd_generate_year_date_ranges(self):
        """Scheduled Action: 00:01 น. 1 ม.ค. เวลาไทย สร้าง Sub Sequences ของปีนั้น"""
        return self._npd_generate_year_date_ranges(self._npd_today().year, commit=True)

    @api.model
    def _npd_generate_year_date_ranges(self, year, commit=False):
        """สร้าง Sub Sequences ปี ``year`` ให้ทุก Sequence ตามรูปแบบชุดล่าสุดของปีก่อน

        :param commit: commit ทีละ Sequence (ใช้ตอนรันจาก cron) ถ้ารันนาน/โดน kill
                       กลางทาง รอบถัดไปจะทำต่อจากที่ค้าง เพราะข้ามวันที่มีช่วงแล้ว
        :return: list ของ (sequence, status, จำนวนที่สร้าง, รายละเอียด)
        """
        results = []
        for sequence in self.sudo().search([('use_date_range', '=', True)], order='id'):
            try:
                with self.env.cr.savepoint():
                    status, count, detail = sequence._npd_generate_date_ranges_for_year(year)
            except Exception as error:
                _logger.exception('npd_sequence_auto_year_range: %s (id %s) failed',
                                  sequence.name, sequence.id)
                status, count, detail = 'error', 0, str(error)
            results.append((sequence, status, count, detail))
            if commit and count:
                self.env.cr.commit()
        self._npd_log_summary(year, results)
        return results

    def _npd_base_batch(self, base_year):
        """ชุด Sub Sequences ล่าสุดของปีฐานที่ครบทั้งปี

        ชุด = ช่วงที่สร้างใน transaction เดียวกัน (create_date เท่ากัน) เช่นกดปุ่ม
        Generate Sub Sequences ครั้งเดียว ถ้าเคยสร้างใหม่ทับ (เปลี่ยนรูปแบบกลางปี)
        จะได้ชุดที่ใหม่กว่า ส่วนชุดที่ไม่ครบปี (เพิ่มมือทีละวัน) ข้ามไป

        :return: (period, ranges) / (None, ranges ที่มี prefix) ถ้าไม่มีชุดที่ครบ
        """
        self.ensure_one()
        ranges = self.env['ir.sequence.date_range'].search([
            ('sequence_id', '=', self.id),
            ('date_from', '>=', date(base_year, 1, 1)),
            ('date_to', '<=', date(base_year, 12, 31)),
        ]).filtered(lambda r: r.prefix or r.suffix)
        batches = defaultdict(list)
        for date_range in ranges:
            batches[date_range.create_date].append(date_range)
        for created in sorted(batches, reverse=True):
            batch = batches[created]
            period = detect_period([(r.date_from, r.date_to) for r in batch], base_year)
            if period:
                return period, batch
        return None, ranges

    def _npd_generate_date_ranges_for_year(self, year):
        """:return: (status, จำนวนที่สร้าง, รายละเอียด)"""
        self.ensure_one()
        period, batch = self._npd_base_batch(year - 1)
        if not batch:
            return 'skip', 0, 'ปี %s ไม่มี Sub Sequences ที่มี prefix/suffix' % (year - 1)
        if not period:
            return 'attention', 0, 'ปี %s มี prefix แต่ไม่มีชุดไหนครบทั้งปี (%s ช่วง) ต้องสร้างเอง' % (
                year - 1, len(batch))

        # วันที่อ้างอิงของ prefix = date_to ตรงกับปุ่ม Generate (รายเดือนใช้วันสิ้นเดือน)
        prefix_fmt = infer_format([(r.date_to, r.prefix) for r in batch])
        suffix_fmt = infer_format([(r.date_to, r.suffix) for r in batch])
        if prefix_fmt is None or suffix_fmt is None:
            sample = batch[-1]
            return 'attention', 0, 'เดารูปแบบไม่ได้ (เช่น %s = %r) ต้องสร้างเอง' % (
                sample.date_to, sample.prefix)

        existing = self.env['ir.sequence.date_range'].search([
            ('sequence_id', '=', self.id),
            ('date_from', '<=', date(year, 12, 31)),
            ('date_to', '>=', date(year, 1, 1)),
        ])
        covered = set()
        for date_range in existing:
            day = date_range.date_from
            while day <= date_range.date_to:
                covered.add(day)
                day += timedelta(days=1)

        periods = year_periods(year, period)
        DateRange = self.env['ir.sequence.date_range'].sudo()
        created = 0
        for date_from, date_to in periods:
            if any(date_from + timedelta(days=i) in covered
                   for i in range((date_to - date_from).days + 1)):
                continue
            DateRange.create({
                'sequence_id': self.id,
                'date_from': date_from,
                'date_to': date_to,
                'prefix': render(prefix_fmt, date_to) or False,
                'suffix': render(suffix_fmt, date_to) or False,
            })
            created += 1

        example = render(prefix_fmt, periods[0][1])
        detail = '%s: prefix %s (เช่น %s)' % (
            {'day': 'รายวัน', 'month': 'รายเดือน', 'year': 'ทั้งปี'}[period],
            describe(prefix_fmt), example or '-')
        if suffix_fmt:
            detail += ' suffix %s' % describe(suffix_fmt)
        skipped = len(periods) - created
        if skipped:
            blank = existing.filtered(lambda r: not r.prefix and not r.suffix)
            detail += ' | ข้าม %s ช่วงที่มีอยู่แล้ว' % skipped
            if blank:
                # Odoo สร้างช่วงไม่มี prefix เองเมื่อมีเอกสารก่อน cron รัน
                return 'attention', created, detail + ' (มีช่วงไม่มี prefix %s ช่วง ต้องตรวจ)' % len(blank)
        return ('created' if created else 'exists'), created, detail

    @api.model
    def _npd_log_summary(self, year, results):
        created = [r for r in results if r[1] == 'created']
        attention = [r for r in results if r[1] in ('attention', 'error')]
        exists = [r for r in results if r[1] == 'exists']
        lines = [
            'สร้าง Sub Sequences ปี %s (รูปแบบจากชุดล่าสุดของปี %s)' % (year, year - 1),
            'สร้างใหม่ %s Sequence รวม %s ช่วง | มีครบอยู่แล้ว %s | ต้องตรวจ %s | ข้าม (ไม่มี prefix) %s' % (
                len(created), sum(r[2] for r in results), len(exists), len(attention),
                len([r for r in results if r[1] == 'skip'])),
        ]
        for title, rows in (('ต้องตรวจ', attention), ('สร้างใหม่', created)):
            if rows:
                lines.append('--- %s ---' % title)
                lines += ['[%s] %s: %s %s' % (seq.id, seq.name, count and '+%s ช่วง,' % count or '', detail)
                          for seq, _status, count, detail in rows]
        message = '\n'.join(lines)
        _logger.info('npd_sequence_auto_year_range\n%s', message)
        self.env['ir.logging'].sudo().create({
            'name': 'npd_sequence_auto_year_range',
            'type': 'server',
            'dbname': self.env.cr.dbname,
            'level': 'WARNING' if attention else 'INFO',
            'message': message,
            'path': __name__,
            'func': '_npd_generate_year_date_ranges',
            'line': '0',
        })
        return message
