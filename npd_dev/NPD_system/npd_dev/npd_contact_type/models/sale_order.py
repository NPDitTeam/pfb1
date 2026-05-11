# -*- coding: utf-8 -*-
from odoo import models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_invoices(self, grouped=False, final=False):
        """
        Override method เพื่อส่งค่า contact_type และ sales_contact จาก Sale Order ไปยัง Invoice
        """
        # เรียก method เดิม
        invoices = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)
        
        # อัปเดต contact_type และ sales_contact ให้กับ Invoice ที่สร้าง
        for invoice in invoices:
            # หา Sale Order ที่เกี่ยวข้องกับ Invoice นี้
            sale_orders = invoice.line_ids.mapped('sale_line_ids.order_id')
            
            if sale_orders:
                # ใช้ข้อมูลจาก Sale Order แรก (กรณี grouped invoice)
                sale_order = sale_orders[0]
                
                vals = {}
                
                # ส่ง contact_type
                if sale_order.contact_type:
                    vals['contact_type'] = sale_order.contact_type
                
                # ส่ง sales_contact
                if sale_order.sales_contact:
                    vals['sales_contact_id'] = sale_order.sales_contact.id
                
                if vals:
                    invoice.write(vals)
        
        return invoices
