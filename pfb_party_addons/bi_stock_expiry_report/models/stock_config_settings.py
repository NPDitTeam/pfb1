# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockConfigurationSettings(models.TransientModel):
    _inherit = "res.config.settings"

    stock_expiry_days = fields.Integer(string="Generate Report For (Days)")
    include_expiry = fields.Boolean(string='Include Expiry Stock')
    report_type = fields.Selection([('all','All'),('location','Location'),('warehouse','Warehouse')],string='Report Type', default='all')
    location_ids = fields.Many2many('stock.location', 'location_res_rel','loc_id','conf_loc_id',string='Location', store=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'ware_rel', 'ware_id', 'ware_loc_id', string='Warehouse', store=True)
    recipients_ids = fields.Many2many('res.partner', 'res_part_rel', 'part_id', 'conf_part_id', string='Mail Recipients', store=True)


    def get_values(self):
        loc_list= []
        rec_part = []
        ware_list = []
        for i in self.location_ids:
            loc_list.append(i.id)
        for j in self.warehouse_ids:
            ware_list.append(j.id)
        for k in self.recipients_ids:
            rec_part.append(k.id)
        res = super(StockConfigurationSettings, self).get_values()
        stock_expiry_days = self.env['ir.config_parameter'].sudo().get_param('bi_stock_expiry_report.stock_expiry_days')
        include_expiry = self.env['ir.config_parameter'].sudo().get_param('bi_stock_expiry_report.include_expiry')
        report_type = self.env['ir.config_parameter'].sudo().get_param('bi_stock_expiry_report.report_type')
        location_ids = self.env['ir.config_parameter'].sudo().get_param('bi_stock_expiry_report.location_ids')
        warehouse_ids = self.env['ir.config_parameter'].sudo().get_param('bi_stock_expiry_report.warehouse_ids')
        recipients_ids = self.env['ir.config_parameter'].sudo().get_param('bi_stock_expiry_report.recipients_ids')
        res.update(
            stock_expiry_days = int(stock_expiry_days),
            include_expiry = include_expiry,
            report_type = report_type,
            location_ids = [(4, loc_list)],
            warehouse_ids = [(4, ware_list)],
            recipients_ids = [(4, rec_part)],
        )
        return res

    def set_values(self):
        loc_list= []
        rec_part = []
        ware_list = []
        super(StockConfigurationSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('bi_stock_expiry_report.stock_expiry_days', str(self.stock_expiry_days))
        self.env['ir.config_parameter'].sudo().set_param('bi_stock_expiry_report.include_expiry', self.include_expiry)
        self.env['ir.config_parameter'].sudo().set_param('bi_stock_expiry_report.report_type', self.report_type)
        for i in self.location_ids:
            loc_list.append(i.id)
        for j in self.warehouse_ids:
            ware_list.append(j.id)
        for k in self.recipients_ids:
            rec_part.append(k.id)
        self.env['ir.config_parameter'].sudo().set_param('bi_stock_expiry_report.location_ids', loc_list)
        self.env['ir.config_parameter'].sudo().set_param('bi_stock_expiry_report.warehouse_ids', ware_list)
        self.env['ir.config_parameter'].sudo().set_param('bi_stock_expiry_report.recipients_ids', rec_part)
