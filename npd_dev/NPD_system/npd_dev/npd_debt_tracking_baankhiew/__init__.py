# -*- coding: utf-8 -*-
from . import models
from odoo import api, SUPERUSER_ID

# Database ที่อนุญาตให้แสดงเมนูรายงานติดตามหนี้ทั้งหมด
ALLOWED_DATABASES = ['NPD_S_Group_New_V2', 'NPD_S_Group_New']


def _post_init_hook(cr, registry):
    """ซ่อนเมนูรายงานติดตามหนี้ทั้งหมด ถ้าไม่ใช่ database ที่อนุญาต"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    db_name = cr.dbname
    
    if db_name not in ALLOWED_DATABASES:
        # ซ่อนเมนูรายงานติดตามหนี้ทั้งหมด
        menu = env.ref('npd_debt_tracking_baankhiew.menu_npd_debt_report_summary', raise_if_not_found=False)
        if menu:
            menu.write({'active': False})
