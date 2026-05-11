# Copyright (C) Softhealer Technologies.

from odoo import fields, models
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class Attendance(models.Model):
    _inherit = 'hr.attendance'

    def employee_autocheckout(self):
        auto_checkout = self.env["ir.config_parameter"].get_param(
            "sh_all_in_one_hrms.auto_checkout")
        checkout_time = self.env["ir.config_parameter"].get_param(
            "sh_all_in_one_hrms.checkout_time")
        if auto_checkout:
            checkout_after = self.env["ir.config_parameter"].get_param(
                "sh_all_in_one_hrms.checkout_after")
            attendance_records = self.search([('check_out', '=', False)]).filtered(
                lambda a: (datetime.today() - datetime.strptime(str(a.check_in), DEFAULT_SERVER_DATETIME_FORMAT)).
                total_seconds() / 60 >= int(checkout_after))
            if checkout_time:
                for record in attendance_records:
                    record.write({
                        'check_out': record.check_in,
                    })
            else:
                attendance_records.write({
                    'check_out': fields.Datetime.now(),
                })


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    auto_checkout = fields.Boolean("Enable Auto Checkout?", default=False)
    checkout_after = fields.Integer("Checkout After(minutes)")
    checkout_time = fields.Boolean(
        'Write Checkout datetime as same as Check in')

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        config_parameters = self.env["ir.config_parameter"].sudo()
        for record in self:
            config_parameters.set_param("sh_all_in_one_hrms.auto_checkout",
                                        record.auto_checkout or False)
            config_parameters.set_param(
                "sh_all_in_one_hrms.checkout_after", record.checkout_after)
            config_parameters.set_param(
                "sh_all_in_one_hrms.checkout_time", record.checkout_time)

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        config_parameters = self.env["ir.config_parameter"].sudo()
        res.update(
            auto_checkout=config_parameters.get_param(
                "sh_all_in_one_hrms.auto_checkout"),
            checkout_after=int(config_parameters.get_param(
                "sh_all_in_one_hrms.checkout_after", default=0.0)),
            checkout_time=config_parameters.get_param(
                "sh_all_in_one_hrms.checkout_time")
        )
        return res
