# -*- coding: utf-8 -*-
{
    'name': 'VAT Calculate From Total (Purchase)',
    'version': '14.0.2.2.0',
    'category': 'Accounting',
    'summary': 'คำนวณ VAT จากยอดรวม สำหรับ PO, Vendor Bill, Customer Invoice',
    'description': """
        โมดูลนี้จะ override การคำนวณ VAT ใน Purchase Order, Vendor Bill, Customer Invoice
        โดยจะคำนวณภาษีจากยอดรวม (Untaxed Amount) แทนที่จะคำนวณทีละรายการสินค้า

        v2.2.0 (Fix amount_residual stale ตอน post invoice):
        - เพิ่ม SQL UPDATE amount_residual / amount_residual_currency บน
          receivable/payable line (เฉพาะ unreconciled) ภายใน
          _fix_tax_lines_in_db
        - เพิ่ม SQL UPDATE move.amount_residual จาก sum(line.amount_residual)
        - แก้ปัญหา: หลัง post invoice ตอน "ยอดเงินค้างชำระ" ยังเป็น 60.03
          ทั้งที่ amount_total = 60.00 — เพราะ amount_residual เป็น stored
          compute ที่ SQL UPDATE balance ของเราไม่ trigger recompute
        - ขยาย invalidate_cache ให้ครอบ amount_residual และทุก line ของ move

        v2.1.0 (Hybrid: SQL line-level + lightweight ORM total override):
        - เพิ่ม _compute_amount override (lightweight) — ORM-assign เฉพาะ
          amount_untaxed/amount_tax/amount_total หลัง super
          (bi @api.depends ไม่มี 3 ฟิลด์นี้ → ไม่ trigger cascade กลับ)
        - ห้ามแตะ discount_amt_line / amount_price_subtotal_without_discount
          เพราะนั่นคือต้นเหตุ -0.09 drift ใน v1.x
        - เพิ่ม action_post override → call _fix_tax_lines_in_db หลัง super
          เพื่อ guarantee ยอดถูกแม้หลัง bi compute ฟัยร์ตอน post
        - แก้ปัญหา v2.0.0: ตอน post invoice ที่ใช้ npd_rent_price_round
          Method A ทำให้ line.price_subtotal_without_discount = 56.10
          → bi recompute ใช้ค่านั้น → amount_untaxed = 56.10 (ไม่ใช่ 56.07)
          → total = 60.03 (ไม่ใช่ 60.00)

        v2.0.0 (SQL-only mode for account.move):
        - ตัด ORM _compute_amount override ของ account.move ทิ้ง
        - ตัด _vat_from_total_adjust_amounts (ORM write) ทิ้ง
        - เปลี่ยนเป็น SQL-only fix ผ่าน _fix_tax_lines_in_db ตอน create/write
          เพื่อกัน drift กับ npd_rent_price_round + bi_sale_purchase_discount_with_tax
        - ขยาย _fix_tax_lines_in_db ให้ SQL UPDATE ครบ:
          * tax journal line (เดิม)
          * expense rounding line (เดิม)
          * counterpart receivable/payable (เดิม)
          * account_move.amount_untaxed/tax/total (ใหม่)
          * amount_price_subtotal_without_discount (ใหม่ — กัน bi recompute drift)
          * discount_amt_line = 0 (ใหม่ — กัน bi formula ดึง drift กลับมา)
          * amount_price_total_full (ใหม่)
        - depend npd_rent_price_round เพื่อบังคับ MRO ให้ vat_from_total
          รันหลัง npd_rent_price_round (พูดคำสุดท้ายเรื่องยอด)
        - PO (purchase.order) ยังใช้ ORM _amount_all เหมือนเดิม (ไม่ชนกับใคร)

        v1.1.0:
        - รองรับ Customer Invoice (out_invoice, out_refund)
        - รองรับส่วนลดจาก bi_sale_purchase_discount_with_tax
        - ใช้ยอดหลังหักส่วนลด (line.discount_amt) ในการคำนวณ
        - Tax Included: per-line แล้ว sum (ตรงกับ PO)
        - Tax Excluded: sum แล้วคำนวณ tax (ตรงกับ PO)

        v1.0.2:
        - เพิ่ม bi_sale_purchase_discount_with_tax ใน depends
        - override _compute_amount() แทน _recompute_tax_lines()
    """,
    'author': 'NPD Dev',
    'website': '',
    'depends': [
        'purchase',
        'account',
        'bi_sale_purchase_discount_with_tax',
        'npd_rent_price_round',
    ],
    'data': [
        'views/account_move_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
