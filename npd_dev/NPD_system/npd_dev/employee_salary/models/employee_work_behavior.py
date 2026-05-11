# -*- coding: utf-8 -*-
from odoo import models, fields


class EmployeeWorkBehavior(models.Model):
    _name = 'employee.work.behavior'
    _description = 'พฤติกรรมการทำงาน'

    name = fields.Char(string='พฤติกรรมการทำงาน', required=True)
    employee_id = fields.Many2one('employee.salary', string='พนักงาน', ondelete='cascade')


class EmployeeWorkHistoryImage(models.Model):
    _name = 'employee.work.history.image'
    _description = 'รูปภาพประวัติการทำงาน'

    name = fields.Char(string='ชื่อไฟล์')
    image = fields.Binary(string='รูปภาพ', attachment=True, required=True)
    image_preview = fields.Binary(string='ตัวอย่างรูป', related='image', readonly=True)
    employee_id = fields.Many2one('employee.salary', string='พนักงาน', ondelete='cascade')
