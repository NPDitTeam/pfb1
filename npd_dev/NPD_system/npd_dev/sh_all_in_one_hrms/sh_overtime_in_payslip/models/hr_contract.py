# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models


class HrContract(models.Model):
    """
    Employee contract based on the visa, work permits
    allows to configure different Salary structure
    """
    _inherit = 'hr.contract'
    _description = 'Employee Contract'

    overtime_rate_per_hr =fields.Float(string = "OT rate per hour")

    def get_ovetime_data(self, employee,payslip):

        overtime_salary = 0

        overtimes = self.env['sh.hr.overtime'].search([('employee_id','=',employee.id),('state','=','approve')])
        overtimes = overtimes.filtered(lambda x:str(x.from_hrs.date()) >= str(payslip.date_from) and str(x.to_hrs.date()) <= str(payslip.date_to))

        working_day_list = list(set(employee.resource_calendar_id.attendance_ids.mapped('dayofweek')))

        total_hrs_weekday = 0
        total_hrs_weekend = 0

        for overtime in overtimes:
            if str(overtime.from_hrs.weekday()) in working_day_list:
                total_hrs_weekday = total_hrs_weekday + overtime.total_hours
            else:
                total_hrs_weekend = total_hrs_weekend + overtime.total_hours

        
        overtime_weekdays = self.env['sh.overtime.config.weekday'].search([
            ('from_hour','<=',total_hrs_weekday),
            ('to_hour','>',total_hrs_weekday)
        ])
        
        last_weekdays = self.env['sh.overtime.config.weekday'].search([]).sorted(key=lambda r: r.to_hour)
        
        
        overtime_weekends = self.env['sh.overtime.config.weekend'].search([
            ('from_hour','<=',total_hrs_weekend),
            ('to_hour','>',total_hrs_weekend)
        ])
        
        last_weekends = self.env['sh.overtime.config.weekend'].search([]).sorted(key=lambda r: r.to_hour)
        
        if overtime_weekdays:
            overtime_salary = overtime_salary + (self.overtime_rate_per_hr * overtime_weekdays[0].hours_rate_multiplication * total_hrs_weekday)
        elif total_hrs_weekday and not overtime_weekdays:
            overtime_salary = overtime_salary + (self.overtime_rate_per_hr * last_weekdays[-1].hours_rate_multiplication * total_hrs_weekday)
        if overtime_weekends:
            overtime_salary = overtime_salary + (self.overtime_rate_per_hr * overtime_weekends[0].hours_rate_multiplication * total_hrs_weekend)
        elif total_hrs_weekend and not overtime_weekends:
            overtime_salary = overtime_salary + (self.overtime_rate_per_hr * last_weekends[-1].hours_rate_multiplication * total_hrs_weekend)  

        return overtime_salary
        