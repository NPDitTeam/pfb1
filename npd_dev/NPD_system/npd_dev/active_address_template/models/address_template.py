# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ActiveAddressTemplate(models.Model):
    _name = 'active.address.template'
    _description = 'Active Address Template'
    _order = 'name'

    name = fields.Char(
        string='Template Name',
        required=True,
        help='Name of the address template'
    )
    
    address = fields.Text(
        string='Address',
        help='Complete address information'
    )
    address_wt = fields.Text(
        string='Address wt',
        help='Complete address information'
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=False,
        help='Check this box to use this as the active address'
    )

    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Company'
    )

    @api.model
    def create(self, vals):
        # หากเลือก is_active = True ให้ปิด active ของอันที่เหลือ
        if vals.get('is_active'):
            company_id = vals.get('company_id', self.env.company.id)
            self.env['active.address.template'].search([
                ('company_id', '=', company_id),
                ('is_active', '=', True)
            ]).write({'is_active': False})
        
        return super().create(vals)

    def write(self, vals):
        # หากเลือก is_active = True ให้ปิด active ของอันที่เหลือ
        if vals.get('is_active'):
            for record in self:
                self.env['active.address.template'].search([
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id),
                    ('is_active', '=', True)
                ]).write({'is_active': False})
        
        return super().write(vals)

    def get_active_address(self):
        """ดึงที่อยู่ที่ active"""
        active_address = self.search([
            ('is_active', '=', True),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        return active_address
    
    def get_active_address_text(self):
        """ดึงข้อความที่อยู่จากเทมเพลตที่ active"""
        active_address = self.get_active_address()
        if active_address:
            return active_address.address
        return False

    def action_set_active(self):
        """ตั้งให้เป็น active address"""
        self.write({'is_active': True})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Address "{self.name}" is now active',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_set_inactive(self):
        """ปิด active address"""
        self.write({'is_active': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Address "{self.name}" is now inactive',
                'type': 'success',
                'sticky': False,
            }
        }
