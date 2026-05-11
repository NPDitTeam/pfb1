# -*- coding: utf-8 -*-
import requests
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from collections import defaultdict

_logger = logging.getLogger(__name__)

# URL for the new CRUD API
APPROVER_CRUD_API_URL = "https://npdhrms.com/api_approver_relations.php"

class ApproverRelations(models.Model):
    _name = 'approver.relations'
    _description = 'Approver Relations'
    _rec_name = 'user_id'

    user_id = fields.Many2one(
        'employee.salary',
        string='Employee',
        required=True,
        ondelete='cascade'
    )
    department_id = fields.Many2one('hr.department.custom', string='แผนก', related='user_id.department_id', readonly=True)
    position_id = fields.Many2one('hr.position.custom', string='ตำแหน่งผู้อนุมัติ')
    approver_user_id = fields.Many2one(
        'employee.salary',
        string='รายชื่อผู้อนุมัติ',
        domain="[('position_id', '=', position_id)]"
    )

    _sql_constraints = [
        ('user_position_unique', 'unique(user_id, position_id)', 'This approver relation already exists!'),
    ]

    employee_code = fields.Char(related='user_id.employee_code', string='รหัสพนักงาน', store=True, readonly=True)
    approver_employee_code = fields.Char(related='approver_user_id.employee_code', string='รหัสผู้อนุมัติ', store=True,
                                         readonly=True)
    approver_name = fields.Char(related='approver_user_id.firstname', string='ชื่อผู้อนุมัติ', store=True,
                                readonly=True)

    @api.constrains('user_id', 'approver_user_id')
    def _check_unique_approver(self):
        for rec in self:
            if rec.user_id and rec.user_id == rec.approver_user_id:
                raise UserError("A user cannot be their own approver.")

    def _sync_to_api(self, action):
        for rec in self:
            try:
                payload = {
                    'action': action,
                    'values': {
                        'employee_code_user_id': rec.employee_code,
                        'approver_employee_code': rec.approver_employee_code,
                        'position_name': rec.position_id.name if rec.position_id else None,
                    }
                }
                response = requests.post(APPROVER_CRUD_API_URL, json=payload)
                response.raise_for_status()
                api_response = response.json()
                if api_response.get('status') != 'success':
                    _logger.error("API sync failed for record ID %s. Message: %s", rec.id, api_response.get('message'))
                    raise UserError(f"API sync failed: {api_response.get('message') or 'Unknown error'}")

            except requests.exceptions.RequestException as e:
                _logger.error("Failed to connect to API for record ID %s: %s", rec.id, e)
                raise UserError(f"Failed to connect to API: {e}")
            except Exception as e:
                _logger.error("An unexpected error occurred during API sync for record ID %s: %s", rec.id, e)
                raise UserError(f"An unexpected error occurred: {e}")

    @api.model
    def create(self, vals):
        record = super(ApproverRelations, self).create(vals)
        record._sync_to_api('create')
        return record

    def write(self, vals):
        res = super(ApproverRelations, self).write(vals)
        if res:
            self._sync_to_api('update')
        return res

    def unlink(self):
        for rec in self:
            rec._sync_to_api('delete')
        return super(ApproverRelations, self).unlink()
