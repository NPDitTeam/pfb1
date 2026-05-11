# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResBranch(models.Model):
    _inherit = 'res.branch'

    @api.model
    def create(self, vals):
        """ตรวจสอบสิทธิ์ก่อนสร้างข้อมูลสาขา"""
        _logger.info("========== NPD BRANCH SECURITY: CREATE CALLED ==========")
        _logger.info("User: %s, branch_can_create: %s", self.env.user.name, self.env.user.branch_can_create)
        
        if not self.env.user.branch_can_create:
            raise UserError(_('คุณไม่มีสิทธิ์สร้างข้อมูลสาขา กรุณาติดต่อผู้ดูแลระบบ'))
        
        return super(ResBranch, self).create(vals)

    def write(self, vals):
        """ตรวจสอบสิทธิ์ก่อนแก้ไขข้อมูลสาขา"""
        _logger.info("========== NPD BRANCH SECURITY: WRITE CALLED ==========")
        _logger.info("User: %s, branch_can_write: %s", self.env.user.name, self.env.user.branch_can_write)
        
        if not self.env.user.branch_can_write:
            raise UserError(_('คุณไม่มีสิทธิ์แก้ไขข้อมูลสาขา กรุณาติดต่อผู้ดูแลระบบ'))
        
        return super(ResBranch, self).write(vals)

    def unlink(self):
        """ตรวจสอบสิทธิ์ก่อนลบข้อมูลสาขา"""
        _logger.info("========== NPD BRANCH SECURITY: UNLINK CALLED ==========")
        _logger.info("User: %s, branch_can_delete: %s", self.env.user.name, self.env.user.branch_can_delete)
        
        if not self.env.user.branch_can_delete:
            raise UserError(_('คุณไม่มีสิทธิ์ลบข้อมูลสาขา กรุณาติดต่อผู้ดูแลระบบ'))
        
        return super(ResBranch, self).unlink()
