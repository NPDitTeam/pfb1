# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    merge_type = fields.Selection([
        ("nothing_new", "New Order and Do Nothing with selected picking orders"),
        ("cancel_new", "New Order and Cancel selected picking orders"),
        ("remove_new", "New Order and Remove selected picking orders"),
        ("nothing_existing", "Existing Order and Do Nothing with selected picking orders"),
        ("cancel_existing", "Existing Order and Cancel selected picking orders"),
        ("remove_existing", "Existing Order and Remove selected picking orders"),
    ], default='nothing_new', string="Default Merge Type")
    notify_in_chatter = fields.Boolean('Notify in Chatter ?')
    sh_stock_sub_merge_qty = fields.Boolean(
        string="  Subtract Merged Quantity")


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    merge_type = fields.Selection(
        related='company_id.merge_type', string="Default Merge Type", readonly=False)
    notify_in_chatter = fields.Boolean(
        'Notify in Chatter ?', related='company_id.notify_in_chatter', readonly=False)
    sh_stock_sub_merge_qty = fields.Boolean(
        related="company_id.sh_stock_sub_merge_qty", string=" Subtract Merged Quantity", readonly=False)
