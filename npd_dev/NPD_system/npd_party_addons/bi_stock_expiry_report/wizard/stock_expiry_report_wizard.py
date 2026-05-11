# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
################################################################################

from odoo import models, fields, api, _
import io
from odoo.exceptions import except_orm
from datetime import datetime,date,timedelta
import collections
import base64
import time
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
try:
    import xlwt
except ImportError:
    xlwt = None

class stock_expiry_report_wizard(models.TransientModel):
    _name = 'stock.expiry.report.wizard'

    stock_expiry_days = fields.Integer(string="Generate Report For (Days)")
    include_expiry = fields.Boolean(string='Include Expiry Stock')
    report_type = fields.Selection([('all','All'),('location','Location'),('warehouse','Warehouse')],string='Report Type', default='all')
    location_ids = fields.Many2many('stock.location', 'location_wiz_rel','loc_id','wiz_id',string='Location')
    warehouse_ids = fields.Many2many('stock.warehouse', 'wh_wiz_rel_expiry', 'wh', 'wiz', string='Warehouse')
    
    def get_warehouse(self):
        if self.warehouse_ids:
            l1 = []
            l2 = []
            for i in self.warehouse_ids:
                obj = self.env['stock.warehouse'].search([('id', '=', i.id)])
                for j in obj:
                    l2.append(j.lot_stock_id.id)
            return l2
        return []

    def get_locations(self):
        if self.location_ids:
            l1 = []
            l2 = []
            for i in self.location_ids:
                obj = self.env['stock.location'].search([('id', '=', i.id)])
                for j in obj:
                    l2.append(j.id)
            return l2
        return []

      
    def print_expiry_report_pdf(self):
        datas = {
            'ids': self._ids,
            'model': 'stock.expiry.report.wizard',
            'stock_expiry_days':self.stock_expiry_days,
            'include_expiry':self.include_expiry,
            'report_type':self.report_type,
            'location_ids':self.get_locations(),
            'warehouse_ids':self.get_warehouse(),
            }

        return self.env.ref('bi_stock_expiry_report.report_expiry_print').report_action(self,data=datas)

    def get_stock_expiry_data(self):
        lines = []
        loc_list = []
        ware_list = []
        lot_obj = self.env['stock.production.lot']
        quant_obj = self.env['stock.quant']
        product_ids = self.env['product.product'].search([])

        current_date = time.strftime(DEFAULT_SERVER_DATE_FORMAT)

        diff = (date.today() + timedelta(days=self.stock_expiry_days)).strftime(DEFAULT_SERVER_DATE_FORMAT)
        for product in product_ids:
            if self.report_type == 'location':
                for loc in self.location_ids:
                    loc_list.append(loc.id)
                quants = quant_obj.search([('product_id','=',product.id),('removal_date','<=',current_date),('location_id','in',loc_list)])
            if self.report_type == 'warehouse':
                for ware in self.warehouse_ids:
                    ware_list.append(ware.lot_stock_id.id)
                quants = quant_obj.search([('product_id','=',product.id),('removal_date','<=',current_date),('location_id','in',ware_list)])
            if self.report_type == 'all':
                quants = quant_obj.search([('product_id','=',product.id),('removal_date','<=',current_date)])

            if quants:
                for i in quants:
                    vals = {
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
        return lines
            
      
    def print_expiry_excel_report(self):
        filename = 'Stock Expiry Report.xls'
        l1 = []
        days = str(self.stock_expiry_days) + 'Days'
        workbook = xlwt.Workbook()
        stylePC = xlwt.XFStyle()
        alignment = xlwt.Alignment()
        alignment.horz = xlwt.Alignment.HORZ_CENTER
        fontP = xlwt.Font()
        fontP.bold = True
        fontP.height = 200
        stylePC.font = fontP
        stylePC.num_format_str = '@'
        stylePC.alignment = alignment
        
        style1 = xlwt.XFStyle()
        style1.num_format_str = 'DD-MM-YY'
        
        style_title = xlwt.easyxf("font:height 300; font: name Liberation Sans, bold on,color black; align: horiz center;pattern: pattern solid, fore_colour aqua;")
        style_table_header = xlwt.easyxf("font:height 200; font: name Liberation Sans, bold on,color black; align: horiz center")
        style_table_title = xlwt.easyxf("font:height 250; font: name Liberation Sans, bold on,color black; align: horiz center")
        style_table_header_left = xlwt.easyxf("font:height 200; font: name Liberation Sans, bold on,color black; align: horiz left")

        style = xlwt.easyxf("font:height 200; font: name Liberation Sans,color black;")
        style_center = xlwt.easyxf("font:height 200; font: name Liberation Sans,color black;align: horiz center")
        worksheet = workbook.add_sheet('Sheet 1')

        worksheet.write_merge(0, 0, 0, 8, "รายละเอียดของคงเหลือที่ขอขยายระยะเวลาการเก็บในเขตปลอดอากร/เขตประกอบการเสรี", style=style_table_title)
        worksheet.write_merge(1, 1, 0, 6, "                               ชื่อบริษัท " + self.env.company.name, style=style_table_header_left)
        worksheet.write_merge(2, 2, 0, 6, "                               เลขทะเบียนสิทธิประโยชน์ " , style=style_table_header_left)
        ranges = self.env["date.range"].search([('date_start', '<=', fields.Date.to_string(date.today())),("date_end", ">=", fields.Date.to_string(date.today())),],limit=1)
        if ranges:
            worksheet.write_merge(3, 3, 0, 6, "                               ประจำงวด " + ranges.name + "   ตั้งแต่วันที่ " + ranges.date_start.strftime('%d-%m-%Y') + "   ถึงวันที่ " + ranges.date_end.strftime('%d-%m-%Y'), style=style_table_header_left)
        else:    
            worksheet.write_merge(3, 3, 0, 6, "                               ประจำงวด                       ตั้งแต่วันที่                                                  ถึงวันที่ ", style=style_table_header_left)
        #worksheet.write_merge(2, 3, 0, 0, "Duration", style=style_table_header)
        #worksheet.write_merge(2, 3, 1, 1, days, style=style_table_header)
        #เลขทะเบียนสิทธิประโยชน์ 
        #ประจำงวด
        if self.include_expiry:
            worksheet.write_merge(4, 4, 0, 6, "                               Including Expiry Stock", style=style_table_header_left)
        worksheet.write(6, 0, 'ลำดับที่', style_table_header)
        worksheet.write(6, 1, 'ชื่อวัตถุดิบ/สินค้า', style_table_header)
        worksheet.write(6, 2, 'รหัสวัตถุดิบ/สินค้า', style_table_header)
        worksheet.write(6, 3, 'เลขที่ใบขนสินค้า', style_table_header)
        worksheet.write(6, 4, 'ปริมาณ', style_table_header)
        worksheet.write(6, 5, 'หน่วยนับ', style_table_header)
        worksheet.write(6, 6, 'วันที่นำเข้าเก็บ', style_table_header)
        worksheet.write(6, 7, 'วันครบกำหนด', style_table_header)
        worksheet.write(6, 8, 'หมายเหตุ', style_table_header)
        worksheet.col(1).width = 12000
        worksheet.col(2).width = 5500
        worksheet.col(3).width = 5500
        worksheet.col(6).width = 5500
        worksheet.col(7).width = 5500
        worksheet.col(8).width = 8000
        worksheet.row(0).height = 500
        get_line = self.get_stock_expiry_data()


        prod_row = 7
        prod_col = 0
        count = 1
        for each in get_line:
            worksheet.write(prod_row, prod_col, count, style_center)
            worksheet.write(prod_row, prod_col+1, each['name'], style)
            worksheet.write(prod_row, prod_col+2, each['product_id'].default_code or '', style_center)
            worksheet.write(prod_row, prod_col+3, each['lot_id'], style_center)
            worksheet.write(prod_row, prod_col+4, each['quantity'], style)
            worksheet.write(prod_row, prod_col+5, each['product_uom_id'].name, style_center)
            if each['in_date']:
                worksheet.write(prod_row, prod_col+6, each['in_date'].strftime('%d-%m-%Y'),style_center)
            if each['remove_date']:
                worksheet.write(prod_row, prod_col+7, each['remove_date'].strftime('%d-%m-%Y'),style_center)
            worksheet.write(prod_row, prod_col+8, each['remark'] or '', style)
            prod_row = prod_row + 1
            count = count+1


        fp = io.BytesIO()
        workbook.save(fp)
        
        export_id = self.env['expiry.report.excel'].create({'excel_file': base64.encodestring(fp.getvalue()), 'file_name': filename})
        res = {
                'view_mode': 'form',
                'res_id': export_id.id,
                'res_model': 'expiry.report.excel',
                'type': 'ir.actions.act_window',
                'target':'new'
            }
        return res


class stock_expiry_excel(models.TransientModel):

    _name = "expiry.report.excel"


    excel_file = fields.Binary('Excel Report for Stock Expiry', readonly =True)
    file_name = fields.Char('Excel File', size=64)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:# 

