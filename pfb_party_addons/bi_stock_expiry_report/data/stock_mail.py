# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo import SUPERUSER_ID
import time
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime,date,timedelta


class StockExpiry(models.Model):
    _name = "stock.expiry.report"
    _inherit = ['mail.thread',]

    stock_expiry_days = fields.Integer(string="Generate Report For (Days)")
    include_expiry = fields.Boolean(string='Include Expiry Stock')
    report_type = fields.Selection([('all','All'),('location','Location'),('warehouse','Warehouse')],string='Report Type', default='all')
    location_ids = fields.Many2many('stock.location', 'location_res_rel_ex','loc_id','conf_loc_id',string='Location', store=True)
    warehouse_ids = fields.Many2many('stock.warehouse', 'ware_rel_ex', 'ware_id', 'ware_loc_id', string='Warehouse', store=True)
    recipients_ids = fields.Many2many('res.partner', 'res_part_rel_ex', 'part_id', 'conf_part_id', string='Mail Recipients', store=True)


    
    def stock_expiry_report_send(self):
        config_setting = self.search([], limit=1, order="id desc")
        super_user = self.env['res.users'].browse(SUPERUSER_ID)
        if not config_setting.stock_expiry_days:
            raise Warning('Please Configure Stock Expiry Email Days In Configuration')
        if config_setting.report_type == 'all':
            template_id = self.env.ref('bi_stock_expiry_report.email_template_stock_expired_remainder')
        if config_setting.report_type == 'location':
            template_id = self.env.ref('bi_stock_expiry_report.email_template_stock_expired_remainder_location')
        if config_setting.report_type == 'warehouse':
            template_id = self.env.ref('bi_stock_expiry_report.email_template_stock_expired_remainder_warehouse')
        if template_id:
            for email_to_custom in config_setting.recipients_ids:
                email_template_obj = self.env['mail.template'].browse(template_id.id)
                values = email_template_obj.generate_email(super_user.id, fields=None)
                values['email_from'] = super_user.email
                values['email_to'] = email_to_custom.id
                values['res_id'] = False
                mail_mail_obj = self.env['mail.mail']
                msg_id = mail_mail_obj.create(values)
                if msg_id:
                    mail_mail_obj.send([msg_id])


    def get_stock_expiry_data_location(self):
        vals = {}
        lines = []
        loc_list = []
        ware_list = []
        lot_obj = self.env['stock.production.lot']
        quant_obj = self.env['stock.quant']
        product_ids = self.env['product.product'].search([])
        config_setting = self.search([], limit=1, order="id desc")
        current_date = time.strftime(DEFAULT_SERVER_DATE_FORMAT)
        diff = (date.today() + timedelta(days=config_setting.stock_expiry_days)).strftime(DEFAULT_SERVER_DATE_FORMAT)
        for i in config_setting.location_ids:
            loc_list.append(i.id)
        for product in product_ids:
            quants = quant_obj.search([('product_id','=',product.id),('removal_date','<=',current_date),('location_id','in',loc_list)])
            count = 1
            if quants:
                for i in quants:
                    vals = {'no':count,
                            'name':i.product_id.name,
                            'lot_id':i.lot_id.name,
                            'quantity':i.quantity,
                            'remove_date':i.removal_date
                            }
                    lines.append(vals)
                    count = count + 1
        return lines

    def get_stock_expiry_data_all(self):
        vals = {}
        lines = []
        loc_list = []
        ware_list = []
        lot_obj = self.env['stock.production.lot']
        quant_obj = self.env['stock.quant']
        product_ids = self.env['product.product'].search([])
        config_setting = self.search([], limit=1, order="id desc")
        current_date = time.strftime(DEFAULT_SERVER_DATE_FORMAT)
        diff = (date.today() + timedelta(days=config_setting.stock_expiry_days)).strftime(DEFAULT_SERVER_DATE_FORMAT)
        for product in product_ids:
            quants = quant_obj.search([('product_id','=',product.id),('removal_date','<=',current_date)])
            count = 1
            if quants:
                for i in quants:
                    vals = {'no':count,
                            'name':i.product_id.name,
                            'lot_id':i.lot_id.name,
                            'quantity':i.quantity,
                            'remove_date':i.removal_date
                            }
                    lines.append(vals)
                    count = count + 1
        return lines

    def get_stock_expiry_data_warehouse(self):
        vals = {}
        lines = []
        loc_list = []
        ware_list = []
        lot_obj = self.env['stock.production.lot']
        quant_obj = self.env['stock.quant']
        product_ids = self.env['product.product'].search([])
        config_setting = self.search([], limit=1, order="id desc")
        current_date = time.strftime(DEFAULT_SERVER_DATE_FORMAT)
        diff = (date.today() + timedelta(days=config_setting.stock_expiry_days)).strftime(DEFAULT_SERVER_DATE_FORMAT)
        for i in config_setting.warehouse_ids:
            ware_list.append(i.id)
        for product in product_ids:
            quants = quant_obj.search([('product_id','=',product.id),('removal_date','<=',current_date),('location_id','in',ware_list)])
            count = 1
            if quants:
                for i in quants:
                    vals = {'no':count,
                            'name':i.product_id.name,
                            'lot_id':i.lot_id.name,
                            'quantity':i.quantity,
                            'remove_date':i.removal_date
                            }
                    lines.append(vals)
                    count = count + 1
        return lines
    
