# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
################################################################################
from odoo import models, fields, api, _
import time
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime,date,timedelta

class report_expiry_pdf(models.AbstractModel):
    _name = 'report.bi_stock_expiry_report.report_expiry_pdf'

    
    def _get_report_values(self, docids, data=None):
        data = data if data is not None else {}
        ranges = self.env["date.range"].search([('date_start', '<=', fields.Date.to_string(date.today())),("date_end", ">=", fields.Date.to_string(date.today())),],limit=1)
        return {
                   'doc_model': 'stock.expiry.report.wizard',
                   'data' : data,
                   'ranges' : ranges,
                   'get_stock_expiry_data' : self.get_stock_expiry_data,
                   }

    def get_stock_expiry_data(self,data):
        vals = {}
        lines = []
        loc_list = []
        ware_list = []
        lot_obj = self.env['stock.production.lot']
        quant_obj = self.env['stock.quant']
        product_ids = self.env['product.product'].search([])
        current_date = time.strftime(DEFAULT_SERVER_DATE_FORMAT)
        diff = (date.today() + timedelta(days=data['stock_expiry_days'])).strftime(DEFAULT_SERVER_DATE_FORMAT)
        for product in product_ids:
            if data['report_type'] == 'location':
                quants = quant_obj.search([('product_id','=',product.id),('removal_date','<=',current_date),('location_id','in',data['location_ids'])])
            if data['report_type'] == 'warehouse':
                quants = quant_obj.search([('product_id','=',product.id),('removal_date','<=',current_date),('location_id','in',data['warehouse_ids'])])
            if data['report_type'] == 'all':
                quants = quant_obj.search([('product_id','=',product.id),('removal_date','<=',current_date)])
            count = 1
            if quants:
                for i in quants:
                    vals = {
                        'no':count,
                        'name':i.product_id.name,
                        'lot_id':i.lot_id.name,
                        'quantity':i.quantity,
                        'product_uom_id':i.product_uom_id,
                        'product_id':i.product_id,
                        'remove_date':i.removal_date,
                        'in_date':i.in_date,
                        'remark':i.remark
                    }
                    lines.append(vals)
                    count = count + 1
        return lines

    

    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
