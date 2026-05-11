# -*- coding: utf-8 -*-

import requests
import json
import logging
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ============================================================
# Config สำหรับ DB ปลายทางทั้งหมด
# login/password เหมือนกันทุก DB
# ============================================================
REMOTE_LOGIN = 'Npd_admin'
REMOTE_PASSWORD = '1234'
REMOTE_URL = 'https://npderp.com'

REMOTE_DB_LIST = [
    'NPD_Bangkok_New',
    'NPD_Intertrading_New',
    'NPD_Logistics_New',
    'NPD_S_Group_New_V2',
    'NPD_Steeltech_New',
]


def _build_db_configs():
    """สร้าง config list จาก DB list"""
    return [
        {
            'name': db,
            'url': REMOTE_URL,
            'db': db,
            'login': REMOTE_LOGIN,
            'password': REMOTE_PASSWORD,
        }
        for db in REMOTE_DB_LIST
    ]


class EmployeeSalarySync(models.Model):
    _inherit = 'employee.salary'

    sync_status = fields.Selection(
        [
            ('pending', 'รอดำเนินการ'),
            ('success', 'สำเร็จ'),
            ('failed', 'ไม่สำเร็จ'),
        ],
        string='สถานะ Sync',
        default='pending',
        tracking=True,
    )
    sync_message = fields.Text(string='ผลการ Sync')
    sync_date = fields.Datetime(string='วันที่ Sync ล่าสุด')

    # ----------------------------------------------------------
    # Private: JSON-RPC helpers
    # ----------------------------------------------------------
    def _authenticate_remote_db(self, config):
        """
        Authenticate กับ DB ปลายทาง
        Return: (requests.Session, error_message)
        - สำเร็จ: (session, None)
        - ไม่สำเร็จ: (None, error_message)
        """
        session = requests.Session()
        url = '{}/web/session/authenticate'.format(config['url'])
        payload = {
            'jsonrpc': '2.0',
            'params': {
                'db': config['db'],
                'login': config['login'],
                'password': config['password'],
            }
        }
        try:
            resp = session.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            if result.get('error'):
                return None, 'ไม่สามารถเข้าสู่ระบบ DB [%s]: %s' % (
                    config['db'], result['error'].get('message', ''))
            uid = result.get('result', {}).get('uid')
            if not uid:
                return None, 'ไม่สามารถเข้าสู่ระบบ DB [%s]: UID ไม่ถูกต้อง (ตรวจสอบ login/password)' % config['db']
            _logger.info('Authenticated to %s as uid=%s', config['db'], uid)
            return session, None
        except requests.exceptions.ConnectionError:
            return None, 'ไม่สามารถเชื่อมต่อ DB [%s] ที่ %s' % (config['db'], config['url'])
        except requests.exceptions.Timeout:
            return None, 'หมดเวลาเชื่อมต่อ DB [%s]' % config['db']
        except Exception as e:
            return None, 'เกิดข้อผิดพลาดเชื่อมต่อ DB [%s]: %s' % (config['db'], str(e))

    def _rpc_call(self, session, config, model, method, args, kwargs=None):
        """เรียก JSON-RPC call_kw ไปยัง DB ปลายทาง"""
        url = '{}/web/dataset/call_kw'.format(config['url'])
        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': {
                'model': model,
                'method': method,
                'args': args,
                'kwargs': kwargs or {},
            }
        }
        resp = session.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get('error'):
            error_msg = result['error'].get('data', {}).get('message', '')
            raise Exception('RPC Error [%s]: %s' % (config['db'], error_msg))
        return result.get('result')

    def _search_remote_user(self, session, config, firstname, lastname):
        """ค้นหา res.users ใน DB ปลายทาง จาก firstname + lastname"""
        domain = [
            ('firstname', '=', firstname),
            ('lastname', '=', lastname),
        ]
        user_ids = self._rpc_call(session, config, 'res.users', 'search', [domain])
        if not user_ids:
            return []
        users = self._rpc_call(
            session, config, 'res.users', 'read',
            [user_ids, ['id', 'login', 'name', 'firstname', 'lastname', 'employee_code']]
        )
        return users or []

    def _update_remote_employee_code(self, session, config, user_id, employee_code):
        """อัพเดท employee_code ใน res.users ของ DB ปลายทาง"""
        self._rpc_call(
            session, config, 'res.users', 'write',
            [[user_id], {'employee_code': employee_code}]
        )

    # ----------------------------------------------------------
    # Core sync logic: ค้นหาทุก DB จนเจอ
    # ----------------------------------------------------------
    def _sync_one_record_all_dbs(self, record):
        """
        Sync employee_code ของ 1 record โดยค้นหาทุก DB
        - เจอสัก DB เดียว = สำเร็จ
        - ไม่เจอเลย = ไม่สำเร็จ พร้อมแจ้งรายละเอียด
        Return: (success: bool, message: str)
        """
        if not record.employee_code:
            return False, 'ไม่มีรหัสพนักงาน (employee_code) ในระเบียนนี้'
        if not record.firstname or not record.lastname:
            return False, 'ไม่มีชื่อหรือนามสกุลในระเบียนนี้'

        configs = _build_db_configs()
        found_dbs = []          # DB ที่เจอและอัพเดทสำเร็จ
        not_found_dbs = []      # DB ที่ค้นหาได้แต่ไม่เจอ user
        error_dbs = []          # DB ที่เชื่อมต่อ/ค้นหาไม่ได้
        duplicate_dbs = []      # DB ที่เจอซ้ำหลายคน

        for config in configs:
            # Authenticate
            session, auth_err = self._authenticate_remote_db(config)
            if auth_err:
                error_dbs.append((config['db'], auth_err))
                continue

            # Search user
            try:
                users = self._search_remote_user(
                    session, config, record.firstname, record.lastname
                )
            except Exception as e:
                error_dbs.append((config['db'], 'ค้นหาไม่ได้: %s' % str(e)))
                continue

            if not users:
                not_found_dbs.append(config['db'])
                continue

            if len(users) > 1:
                logins = ', '.join([u.get('login', '') for u in users])
                duplicate_dbs.append((config['db'], logins))
                continue

            # Update
            user = users[0]
            try:
                self._update_remote_employee_code(
                    session, config, user['id'], record.employee_code
                )
                found_dbs.append((config['db'], user.get('login', '')))
            except Exception as e:
                error_dbs.append((config['db'], 'อัพเดทไม่ได้: %s' % str(e)))

        # ----- สรุปผล -----
        messages = []

        if found_dbs:
            for db_name, login in found_dbs:
                messages.append(u'✅ [%s] อัพเดทรหัส [%s] สำเร็จ → User: %s' % (
                    db_name, record.employee_code, login))

        if duplicate_dbs:
            for db_name, logins in duplicate_dbs:
                messages.append(u'⚠️ [%s] พบผู้ใช้ซ้ำหลายคน (logins: %s) → ตรวจสอบข้อมูลซ้ำ' % (
                    db_name, logins))

        if error_dbs:
            for db_name, err in error_dbs:
                messages.append(u'❌ [%s] %s' % (db_name, err))

        # ถ้าไม่เจอเลยสักDB → แจ้ง error ละเอียด
        if not found_dbs:
            messages.append('')
            messages.append(u'══ ไม่พบผู้ใช้ "%s %s" ในทุก DB ══' % (
                record.firstname, record.lastname))
            messages.append(u'กรุณาตรวจสอบ:')
            messages.append(u'  1. ชื่อ-นามสกุลใน employee.salary ตรงกับ res.users หรือไม่')
            messages.append(u'  2. ตรวจสอบการสะกดชื่อ (ช่องว่าง, ตัวพิมพ์เล็ก-ใหญ่)')
            messages.append(u'  3. User ถูกสร้างใน DB ปลายทางแล้วหรือยัง')
            messages.append(u'  4. firstname/lastname ใน DB ปลายทางมีค่าหรือไม่ (อาจมีแต่ name)')
            if not_found_dbs:
                messages.append(u'  DB ที่ค้นหาแล้วไม่เจอ: %s' % ', '.join(not_found_dbs))

        success = len(found_dbs) > 0
        return success, '\n'.join(messages)

    # ----------------------------------------------------------
    # Button Actions
    # ----------------------------------------------------------
    def action_sync_employee_code(self):
        """
        ปุ่มกดที่ record เดียว - ค้นหาทุก DB จนเจอ
        ใช้ได้เฉพาะ status = active
        """
        self.ensure_one()

        if self.status != 'active':
            raise UserError('ไม่สามารถอัพเดทได้ - สถานะการใช้งานต้องเป็น "ใช้งาน" เท่านั้น')

        success, msg = self._sync_one_record_all_dbs(self)

        self.write({
            'sync_status': 'success' if success else 'failed',
            'sync_message': msg,
            'sync_date': fields.Datetime.now(),
        })

        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': u'สำเร็จ',
                    'message': msg,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': u'ไม่สำเร็จ',
                    'message': msg,
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_sync_employee_code_batch(self, records=None):
        """
        Sync หลาย records พร้อมกัน (เฉพาะ status = active)
        Return: dict สรุปผล
        """
        if records is None:
            records = self

        # กรองเฉพาะ active
        active_records = records.filtered(lambda r: r.status == 'active')
        skipped = len(records) - len(active_records)

        results = {
            'success_count': 0,
            'failed_count': 0,
            'skipped_count': skipped,
            'messages': [],
        }

        if skipped > 0:
            results['messages'].append(
                u'ข้ามพนักงานที่ไม่ใช่สถานะ "ใช้งาน": %d คน' % skipped
            )

        for record in active_records:
            success, msg = self._sync_one_record_all_dbs(record)
            if success:
                results['success_count'] += 1
                record.write({
                    'sync_status': 'success',
                    'sync_message': msg,
                    'sync_date': fields.Datetime.now(),
                })
            else:
                results['failed_count'] += 1
                record.write({
                    'sync_status': 'failed',
                    'sync_message': msg,
                    'sync_date': fields.Datetime.now(),
                })
            results['messages'].append(
                u'[%s] %s %s → %s' % (
                    record.employee_code or '-',
                    record.firstname or '',
                    record.lastname or '',
                    u'สำเร็จ' if success else u'ไม่สำเร็จ',
                )
            )

        return results

    def action_sync_employee_code_multi(self):
        """
        Server Action: เรียกจาก การดำเนินการ เมื่อติ๊กเลือกหลายคนจาก list
        แสดงผลสรุปผ่าน wizard
        """
        results = self.action_sync_employee_code_batch(self)

        # สร้าง wizard แสดงผลสรุป
        summary_lines = [
            u'=== สรุปผลการอัพเดทรหัสพนักงาน ===',
            u'เลือกทั้งหมด: %d คน' % len(self),
            u'สำเร็จ: %d คน' % results['success_count'],
            u'ไม่สำเร็จ: %d คน' % results['failed_count'],
        ]
        if results.get('skipped_count', 0) > 0:
            summary_lines.append(
                u'ข้าม (ไม่ใช่สถานะใช้งาน): %d คน' % results['skipped_count']
            )
        summary_lines.append('')
        summary_lines.append(u'=== รายละเอียด ===')
        summary_lines.extend(results['messages'])

        wizard = self.env['sync.employee.code.wizard'].create({
            'state': 'done',
            'sync_type': 'all',
            'result_text': '\n'.join(summary_lines),
        })

        return {
            'type': 'ir.actions.act_window',
            'name': u'ผลการอัพเดทรหัสพนักงาน',
            'res_model': 'sync.employee.code.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
