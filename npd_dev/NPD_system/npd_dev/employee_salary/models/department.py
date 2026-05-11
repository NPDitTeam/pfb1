# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, api
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# URL ของ API Endpoint
API_URL = "https://npdhrms.com/api_department.php"


class HrDepartmentCustom(models.Model):
    _name = 'hr.department.custom'
    _description = 'แผนก'
    _order = 'id asc'

    name = fields.Char(string='ชื่อแผนก', required=True)
    is_active = fields.Boolean(string='สถานะ', default=True)

    def _sync_to_api(self, action):
        """
        เมธอดสำหรับส่งข้อมูลไปยัง PHP API Endpoint
        """
        for rec in self:
            try:
                payload = {
                    'action': action,
                    'id': rec.id,
                    'name': rec.name,
                    'is_active': 1 if rec.is_active else 0,
                }

                response = requests.post(API_URL, json=payload, timeout=30)
                response.raise_for_status()

                api_response = response.json()
                if api_response.get('status') == 'success':
                    _logger.info("Successfully synced department to API for record ID %s with action: %s", rec.id, action)
                else:
                    _logger.error("API sync failed for department ID %s. Message: %s", rec.id, api_response.get('message'))

            except requests.exceptions.RequestException as e:
                _logger.error("Failed to connect to API for department ID %s: %s", rec.id, e)
            except Exception as e:
                _logger.error("An unexpected error occurred during API sync for department ID %s: %s", rec.id, e)

    @api.model
    def sync_all_from_api(self):
        """
        เมธอดสำหรับดึงและอัปเดตข้อมูลทั้งหมดจาก PHP API Endpoint
        """
        _logger.info("Starting sync departments from PHP API...")
        try:
            response = requests.get(API_URL, timeout=30)
            response.raise_for_status()

            api_response = response.json()

            if api_response.get('status') == 'success' and 'data' in api_response:
                php_records = api_response['data']
                _logger.info("Successfully fetched %d department records from PHP API.", len(php_records))

                # ดึง ID ทั้งหมดจาก PHP
                php_ids = [int(rec['id']) for rec in php_records]
                
                # ดึงข้อมูลที่มีอยู่ใน Odoo
                existing_records = self.search([])
                existing_ids = existing_records.mapped('id')

                for php_data in php_records:
                    php_id = int(php_data['id'])
                    vals = {
                        'name': php_data.get('name'),
                        'is_active': bool(int(php_data.get('is_active', 1))),
                    }
                    
                    if php_id in existing_ids:
                        # อัปเดตข้อมูลที่มีอยู่
                        existing_rec = self.browse(php_id)
                        existing_rec.with_context(skip_api_sync=True).write(vals)
                    else:
                        # สร้างข้อมูลใหม่
                        self.env.cr.execute("""
                            INSERT INTO hr_department_custom (id, name, is_active, create_uid, write_uid, create_date, write_date)
                            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                        """, (php_id, vals['name'], vals['is_active'], self.env.uid, self.env.uid))
                
                # อัปเดต sequence
                self.env.cr.execute("""
                    SELECT setval('hr_department_custom_id_seq', COALESCE((SELECT MAX(id) FROM hr_department_custom), 1))
                """)
                
                _logger.info("Sync departments completed successfully.")
            else:
                _logger.warning("No data from API or API call failed.")

        except requests.exceptions.RequestException as e:
            _logger.error("Failed to connect to API: %s", e)
        except Exception as e:
            _logger.error("An unexpected error occurred during API sync: %s", e)

    @api.model
    def sync_and_open_view(self):
        """
        เมธอดสำหรับซิงค์ข้อมูลและส่งคืน action เพื่อเปิดหน้า view
        """
        self.sync_all_from_api()
        return {
            'type': 'ir.actions.act_window',
            'name': 'แผนก',
            'res_model': 'hr.department.custom',
            'view_mode': 'tree,form',
            'target': 'current',
        }

    @api.model
    def create(self, vals):
        """
        Override create() method to sync data to API after creation.
        """
        record = super(HrDepartmentCustom, self).create(vals)
        if not self.env.context.get('skip_api_sync'):
            record._sync_to_api('create')
        return record

    def write(self, vals):
        """
        Override write() method to sync data to API after update.
        """
        res = super(HrDepartmentCustom, self).write(vals)
        if res and not self.env.context.get('skip_api_sync'):
            self._sync_to_api('update')
        return res

    def unlink(self):
        """
        Override unlink() method to sync data to API before deletion.
        """
        for rec in self:
            if not self.env.context.get('skip_api_sync'):
                rec._sync_to_api('delete')
        return super(HrDepartmentCustom, self).unlink()
