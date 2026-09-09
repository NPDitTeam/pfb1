# -*- coding: utf-8 -*-
"""รายชื่อธนาคารไทย — ใช้ร่วมกันระหว่าง Odoo และแอป (ส่งผ่าน JSON-RPC)

โครงสร้าง 1 รายการ:
    code  : รหัสธนาคาร (เก็บลง DB ทั้งฝั่ง Odoo และ MySQL ของแอป)
    name  : ชื่อเต็ม ใช้โชว์ใน dropdown
    short : ชื่อย่อ ใช้ประกอบ "หมายเหตุ" อัตโนมัติ เช่น "ธ.ไทยพาณิชย์"

หมายเหตุ: รหัสชุดนี้ต้องตรงกับ employee.salary.bank_name เพื่อให้ดึงบัญชี
ที่ผูกไว้กับพนักงานมาเติมให้อัตโนมัติได้
"""

THAI_BANKS = [
    {'code': 'KBANK', 'name': 'ธนาคารกสิกรไทย', 'short': 'ธ.กสิกรไทย'},
    {'code': 'BBL', 'name': 'ธนาคารกรุงเทพ', 'short': 'ธ.กรุงเทพ'},
    {'code': 'KTB', 'name': 'ธนาคารกรุงไทย', 'short': 'ธ.กรุงไทย'},
    {'code': 'SCB', 'name': 'ธนาคารไทยพาณิชย์', 'short': 'ธ.ไทยพาณิชย์'},
    {'code': 'BAY', 'name': 'ธนาคารกรุงศรีอยุธยา', 'short': 'ธ.กรุงศรีอยุธยา'},
    {'code': 'TTB', 'name': 'ธนาคารทหารไทยธนชาต', 'short': 'ธ.ทหารไทยธนชาต'},
    {'code': 'GSB', 'name': 'ธนาคารออมสิน', 'short': 'ธ.ออมสิน'},
    {'code': 'UOB', 'name': 'ธนาคารยูโอบี', 'short': 'ธ.ยูโอบี'},
    {'code': 'CIMBT', 'name': 'ธนาคารซีไอเอ็มบีไทย', 'short': 'ธ.ซีไอเอ็มบีไทย'},
    {'code': 'KKP', 'name': 'ธนาคารเกียรตินาคินภัทร', 'short': 'ธ.เกียรตินาคินภัทร'},
    {'code': 'LHBANK', 'name': 'ธนาคารแลนด์ แอนด์ เฮ้าส์', 'short': 'ธ.แลนด์ แอนด์ เฮ้าส์'},
    {'code': 'TISCO', 'name': 'ธนาคารทิสโก้', 'short': 'ธ.ทิสโก้'},
    {'code': 'BAAC', 'name': 'ธนาคารเพื่อการเกษตรและสหกรณ์การเกษตร', 'short': 'ธ.ก.ส.'},
    {'code': 'GHB', 'name': 'ธนาคารอาคารสงเคราะห์', 'short': 'ธอส.'},
    {'code': 'ISBT', 'name': 'ธนาคารอิสลามแห่งประเทศไทย', 'short': 'ธ.อิสลาม'},
    {'code': 'PROMPTPAY', 'name': 'พร้อมเพย์ (PromptPay)', 'short': 'พร้อมเพย์'},
]

# [('SCB', 'SCB - ธนาคารไทยพาณิชย์'), ...] — ใช้เป็น selection ของฟิลด์ Odoo
BANK_SELECTION = [(b['code'], '%s - %s' % (b['code'], b['name'])) for b in THAI_BANKS]

BANK_SHORT_BY_CODE = {b['code']: b['short'] for b in THAI_BANKS}
BANK_NAME_BY_CODE = {b['code']: b['name'] for b in THAI_BANKS}


def bank_short_name(code):
    """ชื่อย่อธนาคารสำหรับใส่ในหมายเหตุ — ถ้าไม่รู้จักรหัส คืนรหัสเดิมไป"""
    if not code:
        return ''
    return BANK_SHORT_BY_CODE.get(code, code)
