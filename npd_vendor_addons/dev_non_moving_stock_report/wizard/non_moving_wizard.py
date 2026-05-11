# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016 Devintelle Software Solutions (<http://devintellecs.com>).
#
##############################################################################

from odoo.tools.misc import str2bool, xlwt
from xlsxwriter.workbook import Workbook
import base64
import re,sys
from io import BytesIO
from odoo import api, fields, models
from xlwt import easyxf
from datetime import datetime, timedelta
#from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

class nonemoving_stock(models.TransientModel):

    _name ='nonemoving.stock'
    
    company_id =  fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id, required=1)
    date_from = fields.Date('Date From',required=1)
    date_to = fields.Date('Date To', required=1)
    warehouse_id = fields.Many2one('stock.warehouse','Warehouse',required=True)
    category_id = fields.Many2one('product.category','Category')

    def get_line_data(self):
        self._cr.execute("select DISTINCT product_id from stock_move where date >= %s and date <= %s and company_id = %s and warehouse_id = %s ",(self.date_from,self.date_to,self.company_id.id,self.warehouse_id.id))
        data = [x[0] for x in self._cr.fetchall()]
        
        if self.category_id:
            categ_id = []
            if self.category_id:
                categ_id.append(self.category_id.id)
            if self.category_id and self.category_id.parent_id:
                categ_id.append(self.category_id.parent_id.id)
            if self.category_id and self.category_id.parent_id and self.category_id.parent_id.parent_id:
                categ_id.append(self.category_id.parent_id.parent_id.id)
            
            if self.category_id and self.category_id.parent_id and self.category_id.parent_id.parent_id and self.category_id.parent_id.parent_id.parent_id:
                categ_id.append(self.category_id.parent_id.parent_id.parent_id.id)
            product_id = self.env['product.product'].search([('id','not in',data) , ('categ_id','in',categ_id),])
        else:
            product_id = self.env['product.product'].search([('id','not in',data),])
            
        return product_id



    def print_excel(self):
        
        filename='None Moving Product.xls'
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Listing')
        
        # defining various font styles
        style1= easyxf('font:height 200;align: horiz center;font:bold True;')
        style2= easyxf('font:height 200;align: horiz right;font:bold True;')
        style_2= easyxf('font:height 200;align: horiz right;font:')
        text_center = easyxf('align: horiz center;')
        text_right = easyxf('font:height 200;align: horiz right;font:bold True;')
        
        # setting with of the column
        
        worksheet.col(0).width = 70 * 70
        worksheet.col(1).width = 120 * 120
        worksheet.col(2).width = 70 * 70
        worksheet.col(3).width = 60 * 60
        worksheet.col(4).width = 60 * 60
        worksheet.col(5).width = 60 * 60
        
        
        worksheet.write_merge(2, 2 , 1, 8, "None Moving Product",easyxf('font:height 200;align: horiz center;font: color black; font:bold True;')) 
        worksheet.write(3,0, 'Date From',style1)
        worksheet.write(3,1,self.date_from )
        worksheet.write(4,0, 'Date To',style1)
        worksheet.write(4,1, self.date_to)
        
        worksheet.write(3,4, 'Company',style1)
        worksheet.write(3,5,self.company_id.name)
        worksheet.write(4,4, 'Warehouse',style1)
        worksheet.write(4,5, self.warehouse_id.name)
        
        
        
        
        worksheet.write(6,0, 'Default Code',style1)
        worksheet.write(6,1, 'Product',style1)
        worksheet.write(6,2, 'Location',style1)
        worksheet.write(6,3, 'Quantity',style2)
        worksheet.write(6,4, 'Cost Price',style2)
        worksheet.write(6,5, 'Sale Price',style2)

        seq = 6
        debit_total = []
        credit_total = []
        list_data = self.get_line_data()
        seq = 7
        if list_data:
            for data in list_data:
                worksheet.write(seq,0,data.code)
                worksheet.write(seq,1,data.name)
                worksheet.write(seq,2,data.property_stock_production and data.property_stock_production.name)
                worksheet.write(seq,3,data.qty_available,style_2)
                worksheet.write(seq,4,"%.2f"%data.standard_price,style_2)
                worksheet.write(seq,5,"%.2f"%data.lst_price,style_2)
                seq += 1
        
        
        fp = BytesIO()
        workbook.save(fp)
        export_id = self.env['nonemoving.stock.excel'].create({'excel_file': base64.encodestring(fp.getvalue()), 'file_name': filename})
        fp.close()
        
        return {
            'view_mode': 'form',
            'res_id': export_id.id,
            'res_model': 'nonemoving.stock.excel',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'context': self._context,
            'target': 'new',
            
        }

class nonemoving_stock_excel(models.TransientModel):
    _name= "nonemoving.stock.excel"
    excel_file = fields.Binary('Excel Report')
    file_name = fields.Char('Excel File', size=64)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
