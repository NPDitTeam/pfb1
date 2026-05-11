# -*- coding: utf-8 -*-
#################################################################################
# Author      : Acespritech Solutions Pvt. Ltd. (<www.acespritech.com>)
# Copyright(c): 2012-Present Acespritech Solutions Pvt. Ltd.
# All Rights Reserved.
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AlertReport(models.Model):
    _name = 'alert.report.wizard'

    group_by = fields.Selection(string="Group By", selection=[("category", "Category"), ("location", "Location")],
                                default='location')
    category_ids = fields.Many2many('product.category', string='Product Category')
    location_ids = fields.Many2many('stock.location', string='Product Location', domain=[('usage', '=', 'internal')])

    def action_print_report(self):

        [data] = self.read()
        datas = {'form': data,  # it reads all data from wizard page
                 'ids': self.ids,
                 'model': 'alert.report.wizard'}
        return self.env.ref('aspl_product_alert_qty.action_report_alert_qty_wizard').report_action(self, data=datas)

    @api.model
    def cron_btn_send_mail(self):
        template_id = self.env.ref('aspl_product_alert_qty.mail_template_alert_qty')
        wiz_id = self.env['alert.report.wizard'].create({'group_by': 'location'})
        config_id = self.env['res.config.settings'].search([], limit=1, order="id desc")
        if config_id:
            for each in config_id.alert_user_ids:
                email = each.partner_id.email
                partner_name = each.partner_id.name
                result = template_id.with_context(email_to=email, name=partner_name, wizard_id=wiz_id.id).send_mail(
                    wiz_id.id, force_send=True)
        else:
            raise ValidationError(_("Warning! \nPlease configure the settings first in Settings > Inventory."))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
