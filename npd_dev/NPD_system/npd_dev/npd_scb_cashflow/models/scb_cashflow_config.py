# -*- coding: utf-8 -*-
import re
import json
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ScbCashflowConfig(models.Model):
    _name = 'npd.scb.cashflow.config'
    _description = 'SCB Cash Flow Settings'

    name = fields.Char('Name', default='SCB Cash Flow Settings', required=True)
    # ID ของสเปรดชีต = ส่วนที่อยู่ระหว่าง /d/ กับ /edit ใน URL
    spreadsheet_id = fields.Char(
        'Spreadsheet ID', required=True,
        default='1_7Zr-dtaMrBd_urcFdTmhYVE92MQNyG30mfIXFxgHV0',
        help='ส่วนที่อยู่ใน URL ระหว่าง /d/ และ /edit\n'
             'เช่น https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit')
    data_range = fields.Char('Data Range', default='A2:K', required=True,
                             help='ช่วงข้อมูลของแต่ละแท็บ (ไม่รวมหัวตาราง) เช่น A2:K\n'
                                  'ใช้ร่วมกันทั้ง 3 ธนาคาร (SCB / Kbank / กรุงไทย)')
    service_account_json = fields.Text(
        'Service Account JSON',
        help='วางเนื้อหาไฟล์ JSON ของ Service Account ทั้งไฟล์ที่นี่\n'
             'ดาวน์โหลดจาก Google Cloud Console > IAM & Admin > Service Accounts > Keys > Add key > JSON')
    service_account_email = fields.Char(
        'Service Account Email', compute='_compute_service_account_email', store=False,
        help='แชร์ Google Sheet ให้กับอีเมลนี้ (สิทธิ์ Viewer)')
    auto_sync = fields.Boolean('Auto Sync (Cron)', default=True,
                               help='ให้ Scheduled Action ดึงข้อมูลอัตโนมัติหรือไม่')
    last_sync = fields.Datetime('Last Sync', readonly=True)
    last_error = fields.Text('Last Error', readonly=True)

    @api.depends('service_account_json')
    def _compute_service_account_email(self):
        for rec in self:
            email = False
            if rec.service_account_json:
                try:
                    email = json.loads(rec.service_account_json).get('client_email')
                except Exception:
                    email = False
            rec.service_account_email = email

    @staticmethod
    def _extract_sheet_id(val):
        """รับได้ทั้ง ID ล้วน หรือ URL เต็มของ Google Sheet แล้วตัดเอาเฉพาะ ID"""
        val = (val or '').strip()
        m = re.search(r'/spreadsheets/d/([a-zA-Z0-9\-_]+)', val)
        return m.group(1) if m else val

    @api.onchange('spreadsheet_id')
    def _onchange_spreadsheet_id(self):
        if self.spreadsheet_id:
            self.spreadsheet_id = self._extract_sheet_id(self.spreadsheet_id)

    @api.model
    def create(self, vals):
        if vals.get('spreadsheet_id'):
            vals['spreadsheet_id'] = self._extract_sheet_id(vals['spreadsheet_id'])
        return super().create(vals)

    def write(self, vals):
        if vals.get('spreadsheet_id'):
            vals['spreadsheet_id'] = self._extract_sheet_id(vals['spreadsheet_id'])
        return super().write(vals)

    @api.model
    def _get_config(self):
        """คืนค่ารายการตั้งค่า (singleton) สร้างใหม่ถ้ายังไม่มี"""
        config = self.search([], limit=1)
        if not config:
            config = self.create({'name': 'SCB Cash Flow Settings'})
        return config

    @api.model
    def action_open_config(self):
        config = self._get_config()
        return {
            'type': 'ir.actions.act_window',
            'name': _('ตั้งค่ากระแสเงินสดธนาคาร'),
            'res_model': 'npd.scb.cashflow.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'current',
        }

    def action_sync_now(self):
        self.ensure_one()
        count = self.env['npd.scb.cashflow']._sync_from_sheet()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bank Cash Flow'),
                'message': _('ดึงข้อมูลสำเร็จ %s แถว (ทุกธนาคาร).') % count,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }
