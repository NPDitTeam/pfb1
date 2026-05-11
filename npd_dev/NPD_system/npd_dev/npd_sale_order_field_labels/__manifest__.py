# -*- coding: utf-8 -*-
{
    'name': 'NPD Sale Order Field Labels',
    'version': '14.0.1.1.0',
    'summary': 'ปรับแก้ชื่อฟิลด์และซ่อนฟิลด์ใน Sale Order และ Sale Order Line',
    'description': '''
        โมดูลสำหรับปรับแก้ชื่อฟิลด์ใน Sale Order:
        - Sale Type → ประเภทใบเสนอราคา
        - Objective → จุดประสงค์ในการเช่า
        - Day of Rent → วันที่ต้องเช่า
        - Quotation → เลขใบเสนอราคา
        - Approver → อนุมัติ
        - Delivery Date → วันที่จัดส่ง
        - ซ่อน Delivery Block Reason
        - ซ่อน ประเภทการรับชำระหนี้
        
        ปรับแก้ชื่อฟิลด์ใน Sale Order Line:
        - Day of Rent → จํานวนวันที่เช่า
        - Quantity Rent → จํานวนสินค้า
        - ซ่อน จํานวน (product_uom_qty)
        - Insurance → ค่าประกัน
        - Secondary Qty → น้ําหนักต่อหน่วย
        - ซ่อน Secondary UOM
        - Discount Method → ประเภทการลดราคา
        - Discount Amount → ยอดส่วนลด
        - Delivery Date → วันที่จัดส่งสินค้า
        - ซ่อน Second Price
        - ซ่อน หีบห่อ (product_packaging)
        - Subtotal without Discount → ยอดหลังหักส่วนลด
        - ประเภทส่วนลด selection: ส่วนลดสินค้า → ส่วนลดราคาสินค้า
    ''',
    'category': 'Sales',
    'author': 'NPD',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['sale', 'npd_npd_all_customs', 'pfb_npd_all_customs','pfb_npd_add_date_quatation_order','bi_sale_purchase_discount_with_tax'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
