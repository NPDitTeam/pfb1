# -*- coding: utf-8 -*-
u"""ลบชื่อผู้โอนที่ระบบจำผิดไว้ แล้วให้ตรวจใบที่ได้รับผลกระทบใหม่

ระบบจำชื่อผู้โอนอัตโนมัติทุกครั้งที่จับคู่สำเร็จ เพื่อให้ครั้งหน้าเทียบได้ทันที
แต่เดิมจำจากรายการที่เข้าบัญชี "บริษัทอื่นในเครือ" ด้วย พอจับคู่ผิดหนึ่งครั้ง
ชื่อผิดจะถูกจำไว้ถาวรแล้วย้อนกลับมาทำให้จับคู่ผิดซ้ำด้วยความมั่นใจเต็มร้อย

เกณฑ์ตัดสิน: ดูรายการเดินบัญชีของ "ใบที่เรียนรู้ชื่อนั้นมา" ว่าเข้าบัญชีของ
บริษัทเราหรือไม่ ถ้าไม่ใช่ = จำมาจากการจับคู่ผิด

(เกณฑ์เดิมที่ค้นด้วยชื่อคู่ค้าใช้ไม่ได้ เพราะคู่ค้ารายเดียวกันอาจโอนเข้าบัญชี
 บริษัทเราด้วยจริง ๆ เช่น "บจก. มาดี อิเล็คทร" โอนเข้าอินเตอร์เทรดดิ้งเมื่อ
 24/07 แต่ชื่อนี้ถูกจำผิดไปให้ลูกค้า "นาย มิตร ศิริแก้ว" จากรายการของอีกบริษัท)

ลบเฉพาะชื่อที่ระบบจำเอง (origin='auto') ส่วนที่คนเพิ่มเองไม่แตะต้อง
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Alias = env['npd.scb.counterparty.alias'].with_context(active_test=False)
    Slip = env['npd.scb.payment.slip']

    aliases = Alias.search([('origin', '=', 'auto')])
    if not aliases:
        return

    bad = Alias.browse()
    unknown = 0
    for alias in aliases:
        payment = alias.payment_id
        if not payment:
            unknown += 1
            continue        # ไม่รู้ที่มา ไม่เดา
        rows = Slip.search([
            ('payment_id', '=', payment.id), ('state', '=', 'matched'),
        ]).mapped('statement_id')
        if not rows:
            unknown += 1
            continue
        # เทียบกับบริษัทของใบนั้นเอง (ฐานข้อมูลเดียวมีได้หลายบริษัท)
        names = payment._scb_own_account_names()
        numbers = payment._scb_own_account_numbers()
        if not any(r.belongs_to_company(names, numbers) for r in rows):
            bad |= alias

    if not bad:
        _logger.info(u"SCB: ไม่พบชื่อผู้โอนที่จำผิดไว้ (ตรวจ %s รายการ, "
                     u"ไม่รู้ที่มา %s)", len(aliases), unknown)
        return

    # กันพลาด: ถ้าจะลบเกินครึ่ง แปลว่าตัวเทียบ "บัญชีของบริษัทเรา" น่าจะเพี้ยน
    # (เช่นชื่อบริษัทในระบบเขียนต่างจากในชีตมาก) ไม่ใช่ชื่อที่จำไว้ผิดจริง
    if len(bad) * 2 > len(aliases):
        _logger.warning(
            u"SCB: จะลบชื่อที่จำไว้ %s จาก %s รายการ ซึ่งมากผิดปกติ — "
            u"ข้ามการล้างไว้ก่อน กรุณาตรวจว่าชื่อบริษัทในระบบตรงกับชื่อเจ้าของ "
            u"บัญชีในชีตหรือไม่", len(bad), len(aliases))
        return

    partners = bad.mapped('partner_id')
    _logger.info(u"SCB: ลบชื่อผู้โอนที่จำผิดไว้ %s จาก %s รายการ "
                 u"(ลูกค้า %s ราย): %s", len(bad), len(aliases), len(partners),
                 u', '.join(bad.mapped('name'))[:500])
    bad.unlink()

    # ใบของลูกค้าเหล่านี้ที่เคยตรวจไปแล้ว ต้องตรวจใหม่ด้วยชื่อที่สะอาดแล้ว
    cr.execute("""
        UPDATE npd_scb_payment_slip s
           SET state = 'to_check', statement_id = NULL, reason = NULL
          FROM account_payment p
         WHERE p.id = s.payment_id AND p.partner_id = ANY(%s)
           AND s.state IN ('matched', 'not_found')
    """, [partners.ids])
    cr.execute("""
        UPDATE account_payment
           SET scb_verify_state = 'to_check', scb_verify_attempts = 0,
               scb_verify_reason = NULL, scb_verify_summary = NULL,
               scb_statement_id = NULL
         WHERE partner_id = ANY(%s)
           AND scb_verify_state IN ('success', 'other_company', 'failed')
    """, [partners.ids])
    _logger.info(u"SCB: ตั้งใบรับชำระให้ตรวจใหม่ %s ใบ", cr.rowcount)
