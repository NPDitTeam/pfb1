# -*- coding: utf-8 -*-
u"""ช่วยปิดงบ -- ผู้ช่วยค้นหาสำหรับงานปิดงบสิ้นปี (อ่านอย่างเดียว)

หัวข้อนี้ทำ 4 อย่าง
  1. บอก "ลำดับงาน" ว่าต้องดูเมนูไหนก่อน อะไรหลัง แต่ละเมนูอยู่ที่ไหน เอาไว้ทำอะไร
     -> เส้นทางเมนูไม่ได้เขียนตายไว้ แต่ค้นจาก ir.ui.menu ของฐานนั้นจริง ๆ
        (แต่ละบริษัทติดตั้งโมดูลไม่เท่ากัน เมนูจึงไม่เหมือนกัน) และบอกด้วยว่า
        "ผู้ใช้คนนี้เห็นเมนูนั้นหรือเปล่า" เพราะเมนูปิดงบครึ่งหนึ่งซ่อนถ้าสิทธิ์ไม่พอ
  2. ตรวจว่าปีที่ถามปิดงบสมบูรณ์แล้วหรือยัง "ติดที่รายการไหน" และ "เท่าไหร่ถึงจะถูก"
     -> ตัวตรวจทุกตัวเป็นการอ่านข้อมูลล้วน ไม่มีเส้นทางไหนในไฟล์นี้ที่เขียนข้อมูล
  3. ตอบคำถามอิสระเรื่องปิดงบด้วย AI โดยยึดจาก "คู่มือในโค้ด + ผลตรวจจริง + เมนูจริง"
     เท่านั้น (ห้าม AI แต่งชื่อเมนูหรือแต่งตัวเลขเอง)
  4. ออกไฟล์ Excel ให้ในแชท เอาไปไล่งานต่อได้

ทำไม sudo(): บัญชีส่วนกลางต้องเห็นตัวเลขทั้งบริษัท ถ้ากรองตามสิทธิ์รายคน
ตัวเลขที่ตอบจะไม่ตรงกับงบ ความปลอดภัยอยู่ที่ "อ่านอย่างเดียว" + หัวข้อนี้เปิดให้
เฉพาะคนที่ถูกติ๊กสิทธิ์ไว้ (กลุ่ม group_ai_it_closing)
"""
import calendar
import io
import json
import logging
import re
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.tools.misc import html_escape

try:
    import xlsxwriter
except ImportError:  # pragma: no cover - เครื่องที่ไม่มีไลบรารี
    xlsxwriter = None

_logger = logging.getLogger(__name__)

# จำนวนแถวสูงสุดที่ดึงไปใส่ไฟล์ Excel ต่อหนึ่งชีต
MAX_EXCEL_ROWS = 3000
# จำนวนรายการตัวอย่างที่ยกมาให้ดูในแชท (ในแชทอ่านเยอะไม่ไหว)
SAMPLE_ROWS = 8
# เงินที่ต่างกันน้อยกว่านี้ถือว่าเท่ากัน (เศษปัดของ float)
EPS = 0.005
# ย้อนดูได้กี่ปี ตอนพนักงานถามว่า "แต่ละปีปิดครบไหม"
MAX_YEARS = 6

# คำที่แปลว่า "ขอเป็นไฟล์ Excel"
EXCEL_WORDS = (u'excel', u'xlsx', u'เอ็กเซล', u'เอกเซล', u'ไฟล์แนบ', u'ออกไฟล์',
               u'ส่งไฟล์', u'ขอไฟล์', u'เป็นไฟล์', u'export', u'ดาวน์โหลด', u'โหลดไฟล์')
# คำที่แปลว่า "ช่วยตรวจให้หน่อยว่าปิดงบได้ยัง"
CHECK_WORDS = (u'ตรวจ', u'เช็ค', u'เช็ก', u'ติดอะไร', u'ติดตรงไหน', u'ติดที่ไหน',
               u'ปิดได้ยัง', u'ปิดงบได้ไหม', u'สมบูรณ์', u'ครบไหม', u'พร้อมปิด',
               u'ค้างอะไร', u'เหลืออะไร', u'check', u'status')
# คำที่แปลว่า "ขอดูลำดับขั้นตอน/แผนที่เมนู"
STEP_WORDS = (u'ขั้นตอน', u'ลำดับ', u'เริ่มยังไง', u'เริ่มตรงไหน', u'ทำอะไรก่อน',
              u'แผนที่', u'ภาพรวม', u'roadmap', u'step', u'overview', u'คู่มือ')
# คำที่แปลว่า "เมนูนี้อยู่ไหน"
MENU_WORDS = (u'เมนู', u'อยู่ไหน', u'อยู่ตรงไหน', u'หาไม่เจอ', u'เข้าไปที่ไหน',
              u'menu', u'where')

# ======================================================================
# งานที่ยอมให้ AI "ลงมือแก้" ได้
#
# เกณฑ์ -- ต้องครบทั้ง 3 ข้อ
#   1. เป็นการตั้งค่า ไม่ใช่การลงตัวเลขในบัญชี
#   2. ถอยกลับได้จริง (เก็บค่าเดิมไว้ใน npd.ai.it.closing.fix)
#   3. ไม่ต้องใช้ดุลพินิจทางบัญชี มีคำตอบถูกแบบเดียว
#
# งานที่จงใจไม่ทำให้ เพราะผิดเกณฑ์ (ห้ามเพิ่มโดยไม่ถามฝ่ายบัญชีก่อน)
#   Post/Cancel ใบค้างร่าง · แก้ใบที่เดบิตไม่เท่าเครดิต · กระทบยอด ·
#   ยืนยันสินทรัพย์+คิดค่าเสื่อม · Post ใบปิดบัญชี
# ทั้งหมดนี้จะถูกส่งกลับไปให้พนักงานทำเอง ผ่าน worklist_blocks()
# ======================================================================
FIX_ACTIONS = ('cutoff_journal', 'fiscal_year', 'closing_template', 'lock_date')

FIX_LABEL = {
    'cutoff_journal': u'ตั้งสมุดรายวันสำหรับ Cut-off',
    'fiscal_year': u'สร้างปีบัญชี',
    'closing_template': u'สร้างแม่แบบใบปิดบัญชี',
    'lock_date': u'ตั้งวันที่ล็อกงวด',
}
# คำสั่งให้ลงมือแก้ (ต้องเจอคู่กับคำที่บอกว่าจะแก้อะไร)
FIX_VERBS = (u'ตั้ง', u'เปิด', u'สร้าง', u'ช่วยตั้ง', u'ช่วยสร้าง', u'ตั้งค่า',
             u'แก้ให้', u'ช่วยแก้', u'จัดการให้', u'ทำให้', u'set', u'fix')
UNDO_WORDS = (u'ถอย', u'ยกเลิกที่แก้', u'คืนค่า', u'undo', u'rollback', u'ย้อนกลับ')
ALL_WORDS = (u'ทั้งหมด', u'ทุกอย่าง', u'ทุกรายการ', u'all')

STATUS_LABEL = {'block': u'ต้องแก้ก่อน', 'warn': u'ควรดูก่อนปิด', 'ok': u'ผ่าน',
                'skip': u'ไม่มีข้อมูล'}
STATUS_ICON = {'block': u'🔴', 'warn': u'🟡', 'ok': u'🟢', 'skip': u'⚪'}


# ======================================================================
# คู่มือปิดงบ (ฝังไว้ในโค้ด) -- ใช้ทั้งตอบตรง ๆ และเป็นฐานความรู้ให้ AI
#
# find = คำค้นสำหรับไปหา "เมนูจริง" ใน ir.ui.menu ของฐานนั้น
#        (path ที่เขียนไว้เป็นตัวสำรอง เผื่อฐานไหนเมนูชื่อไม่ตรง)
# ======================================================================
CLOSING_STEPS = [
    {
        'order': 1,
        'key': 'collect',
        'title': u'ตรวจรายการให้ครบ',
        'goal': u'รายการทั้งปีลงบัญชีครบ ไม่มีใบค้างร่าง',
        'why': u'ถ้ามีใบร่างค้างในปีที่จะปิด หน้าปิดงบจะขึ้นกรอบแดงและกดคำนวณไม่ได้',
        'items': [
            {'name': u'เคลียร์ใบค้างร่าง',
             'find': u'Journal Entries',
             'path': u'Accounting > Accounting > Miscellaneous > Journal Entries',
             'what': u'กรอง Draft + ปีที่จะปิด แล้วไล่ Post หรือ Cancel ทีละใบ',
             'pass': u'เหลือ 0 รายการ'},
            {'name': u'ไล่สมุดรายวันทีละเล่ม',
             'find': u'Journals',
             'path': u'Accounting > Accounting > Journals',
             'what': u'ดูว่าเลขที่เอกสารเรียงต่อเนื่อง ไม่ขาดช่วง',
             'pass': u'ไม่มีเลขขาดช่วงที่อธิบายไม่ได้'},
            {'name': u'กระทบยอดลูกหนี้-เจ้าหนี้',
             'find': u'Reconciliation',
             'path': u'Accounting > Accounting > Actions > Reconciliation',
             'what': u'จับคู่ใบแจ้งหนี้กับการรับ/จ่ายชำระที่ยังค้าง',
             'pass': u'เหลือเฉพาะรายการที่ยังค้างชำระจริง'},
            {'name': u'สอบยอดลูกหนี้-เจ้าหนี้คงค้าง',
             'find': u'Customer Aging',
             'path': u'Accounting > Customers > Customer Aging (และ Vendors > Supplier Aging)',
             'what': u'ยอด ณ วันสิ้นปี ต้องตรงกับที่บัญชีคุมไว้',
             'pass': u'ยอดตรงกับทะเบียนคุม'},
            {'name': u'ปิดภาษีให้เรียบร้อย',
             'find': u'Thai Tax Report',
             'path': u'Accounting > Reporting > Thai Tax Report / WT Income Tax Report / ใบแนบ ภงด.',
             'what': u'กระทบภาษีซื้อ-ขายรายเดือนกับที่ยื่นจริง และตรวจ ภงด. ให้ครบ 12 เดือน',
             'pass': u'ครบทุกเดือน ตรงกับที่ยื่น (มีผลกับ Tax Lock Date ในขั้นที่ 4)'},
        ],
    },
    {
        'order': 2,
        'key': 'adjust',
        'title': u'ลงรายการปรับปรุงสิ้นปี',
        'goal': u'รายการที่ไม่ได้เกิดจากการซื้อขายประจำวัน แต่ต้องมีก่อนงบจะถูก',
        'why': u'ตัวเลขต้องนิ่งก่อน ไม่งั้นต้องกลับมาแก้ย้อนหลังหลังปิดไปแล้ว',
        'items': [
            {'name': u'ค่าเสื่อมราคา',
             'find': u'Assets',
             'path': u'Accounting > Assets',
             'what': u'ยืนยันสินทรัพย์ที่ยังเป็นร่าง แล้วสั่ง Compute Assets ให้สร้างใบค่าเสื่อม',
             'pass': u'ค่าเสื่อมลงครบถึงเดือนสุดท้ายของปี และใบ JE ค่าเสื่อม Post หมด'},
            {'name': u'ค้างรับ-ค้างจ่าย / รับ-จ่ายล่วงหน้า',
             'find': u'Cut-off',
             'path': u'Accounting > Accounting > Cut-offs',
             'what': u'Accrued Revenue / Accrued Expense / Prepaid Revenue / Prepaid Expense',
             'pass': u'ลงครบตามที่บัญชีคุมไว้'},
            {'name': u'รายการปรับปรุงอื่น ๆ',
             'find': u'Journals',
             'path': u'Accounting > Accounting > Journals',
             'what': u'เปิดสมุดรายวันเบ็ดเตล็ด (JV) แล้วสร้างใบใหม่ — '
                     u'ปรับสินค้าคงเหลือให้ตรงที่นับจริง · ผลต่างอัตราแลกเปลี่ยน · '
                     u'ค่าเผื่อหนี้สงสัยจะสูญ · ภาษีเงินได้นิติบุคคล (ลงเป็นรายการสุดท้าย)',
             'pass': u'ลงครบและ Post แล้ว'},
            {'name': u'ปรับภาษี (ถ้ามี)',
             'find': u'Tax Adjustments',
             'path': u'Accounting > Accounting > Actions > Tax Adjustments',
             'what': u'ปรับยอดภาษีที่ต่างจากที่ยื่น',
             'pass': u'ยอดภาษีตรงกับแบบที่ยื่น'},
        ],
    },
    {
        'order': 3,
        'key': 'report',
        'title': u'ออกงบมาตรวจ (พิมพ์เก็บก่อนขั้นที่ 4)',
        'goal': u'มีงบฉบับก่อนปิดเก็บไว้เป็นหลักฐาน',
        'why': u'ใบปิดบัญชีในขั้นที่ 4 จะล้างยอดรายได้-ค่าใช้จ่ายเป็นศูนย์ '
               u'ถ้าพิมพ์งบกำไรขาดทุนทีหลังจะได้ 0 ทั้งแผ่น',
        'items': [
            {'name': u'1) งบทดลอง (Trial Balance)',
             'find': u'Trial Balance',
             'path': u'Accounting > Reporting > Dynamic Reports(Wiz) > Trial Balance',
             'what': u'ตัวหลัก เดบิตรวมต้องเท่าเครดิตรวม',
             'pass': u'เดบิต = เครดิต'},
            {'name': u'2) งบกำไรขาดทุน (Profit and Loss)',
             'find': u'Profit and Loss',
             'path': u'Accounting > Reporting > Dynamic Reports(Wiz) > Profit and Loss',
             'what': u'ผลประกอบการทั้งปี',
             'pass': u'พิมพ์เก็บเป็น PDF/Excel แล้ว'},
            {'name': u'3) งบดุล (Balance Sheet)',
             'find': u'Balance Sheet',
             'path': u'Accounting > Reporting > Dynamic Reports(Wiz) > Balance Sheet',
             'what': u'ฐานะ ณ วันสิ้นปี',
             'pass': u'พิมพ์เก็บแล้ว'},
            {'name': u'4) งบกระแสเงินสด (Cash Flow)',
             'find': u'Cash Flow',
             'path': u'Accounting > Reporting > Dynamic Reports(Wiz) > Cash Flow Report',
             'what': u'กระแสเงินสดทั้งปี',
             'pass': u'พิมพ์เก็บแล้ว'},
            {'name': u'5) แยกประเภท (General / Partner Ledger)',
             'find': u'General Ledger',
             'path': u'Accounting > Reporting > Dynamic Reports(Wiz) > General Ledger',
             'what': u'ไว้เจาะดูเมื่อยอดไม่ตรง',
             'pass': u'-'},
        ],
    },
    {
        'order': 4,
        'key': 'close',
        'title': u'ปิดงบจริง และล็อก',
        'goal': u'สร้างใบปิดบัญชี แล้วล็อกไม่ให้ใครแก้ย้อนหลัง',
        'why': u'จบรอบ',
        'items': [
            {'name': u'4.1 สร้างปีบัญชี',
             'find': u'Fiscal Years',
             'path': u'Accounting > Configuration > Accounting > Fiscal Years',
             'what': u'สร้างปีบัญชีของปีที่จะปิด (ชื่อ · วันเริ่ม · วันสิ้นสุด · บริษัท)',
             'pass': u'มีปีบัญชีของปีนั้นในระบบ'},
            {'name': u'4.2 ตั้งแม่แบบใบปิดบัญชี',
             'find': u'Fiscal Year Closing',
             'path': u'Accounting > Configuration > Fiscal Year Closing > Closing templates',
             'what': u'ใส่ Moves configuration + Account mappings (อย่างน้อยบรรทัด '
                     u'Loss & Profit: Source 4%,5%,6% -> Destination บัญชีกำไร(ขาดทุน))',
             'pass': u'มี Account mappings ครบ ไม่งั้นกด Calculate แล้วระบบจะเงียบ ไม่สร้างอะไรเลย'},
            {'name': u'4.3 สร้างรายการปิดงบ',
             'find': u'Fiscal year closings',
             'path': u'Accounting > Accounting > Fiscal year closings',
             'what': u'ใส่ Year -> เลือก Closing template -> Calculate -> กดปุ่ม Moves '
                     u'เทียบกับงบที่พิมพ์ไว้ -> ถ้าตรงจึง Post',
             'pass': u'สถานะเป็น Posted (ถอยกลับได้จนกว่าจะ Post)'},
            {'name': u'4.4 ล็อกวันที่',
             'find': u'lock dates',
             'path': u'Accounting > Accounting > Actions > Update accounting lock dates',
             'what': u'Lock Date for Non-Advisers = สิ้นปี · Lock Date for All Users = ใส่ตอนปิดเสร็จจริง '
                     u'· Tax Lock Date = วันสิ้นงวดภาษีที่ยื่นแล้ว',
             'pass': u'ล็อกถึงวันสิ้นปีที่ปิด'},
        ],
    },
]

# อาการที่เจอบ่อย -> สาเหตุจริง -> วิธีแก้
PITFALLS = [
    (u'กด Recover หลัง Post แล้วนึกว่าถอยกลับแล้ว',
     u'ปุ่ม Recover เปลี่ยนแค่สถานะใบปิดกลับเป็นร่าง '
     u'แต่ไม่ได้ลบใบที่ Post ลงบัญชีไปแล้ว (ทดสอบจริงแล้ว)',
     u'ถ้าจะถอยหลัง Post ต้องกด Cancel (ยกเลิก) ซึ่งจะถอนการกระทบยอด '
     u'ยกเลิกและลบใบปิดออกจากบัญชีให้จริง ยอดจะกลับเป็นเหมือนก่อนปิดทุกบาท '
     u'อันตรายของการกด Recover คือถ้าไปกด Calculate ต่อ จะได้ใบปิดซ้ำสองใบ'),
    (u'ใส่ Source accounts เป็น 4%,5%,6% รวมในบรรทัดเดียว',
     u'ระบบเทียบรหัสบัญชีแบบทีละรูปแบบ (=ilike) ใส่รวมกันจะไม่ตรงบัญชีไหนเลย',
     u'ต้องแยกเป็น 3 บรรทัด บรรทัดละรูปแบบ (4% / 5% / 6%) '
     u'ถ้าใส่รวมกัน กด Calculate แล้วจะได้ใบเปล่าโดยไม่ขึ้น error'),
    (u'หาเมนูปิดงบไม่เจอ',
     u'สิทธิ์ผู้ใช้เป็น Billing ไม่ใช่ Billing Administrator',
     u'ให้ IT ปรับที่ Settings > Users > แท็บ Access Rights > Invoicing = Billing Administrator'),
    (u'กด Calculate แล้วเงียบ ไม่มีอะไรเกิดขึ้น',
     u'แม่แบบใบปิดไม่ได้ใส่ Account mappings',
     u'กลับไปใส่ mapping ที่ Closing templates (ขั้น 4.2)'),
    (u'กด Calculate แล้วขึ้นกรอบแดงยาว',
     u'มีใบร่างค้างในปีที่จะปิด',
     u'กลับไปเคลียร์ใบค้างร่างให้เหลือ 0 (ขั้น 1)'),
    (u'งบกำไรขาดทุนออกมาเป็น 0 ทั้งแผ่น',
     u'พิมพ์งบหลัง Post ใบปิดบัญชีไปแล้ว',
     u'ใบปิดล้างยอด 4xxx/5xxx/6xxx เป็นศูนย์ ต้องพิมพ์งบให้เสร็จก่อนขั้นที่ 4'),
    (u'ปีถัดไปยอดยกมาซ้ำสองเท่า',
     u'ทำบรรทัด Closing แต่ไม่ได้ทำ Opening คู่กัน',
     u'ทำครบทั้งคู่ หรือใช้แค่บรรทัด Loss & Profit บรรทัดเดียว '
     u'(Odoo ยกยอดงบดุลข้ามปีให้เองผ่านบัญชีกำไร/ขาดทุนที่ยังไม่ได้สรุป)'),
    (u'ล็อกแล้วกลับไปแก้รายการไม่ได้',
     u'ตั้ง Lock Date for All Users เร็วเกินไป',
     u'เลื่อนวันออกชั่วคราวที่เมนูเดิม แก้เสร็จแล้วล็อกกลับ'),
]


def fields_now():
    u"""สตริงเวลาใช้เป็นรหัสชุดการแก้ (batch)"""
    return fields.Datetime.now().strftime('%Y%m%d%H%M%S')


def _hint_fix(text):
    return u'<span class="text-muted">%s</span>' % text


def _money(value):
    return u'{:,.2f}'.format(float(value or 0.0))


def _thai_date(value):
    if not value:
        return u'—'
    text = str(value)[:10].split('-')
    return u'%s/%s/%s' % (text[2], text[1], text[0]) if len(text) == 3 else str(value)


class NpdAiItClosing(models.AbstractModel):
    _name = 'npd.ai.it.closing'
    _description = u'ตัวช่วย AI-IT : ช่วยปิดงบ (ค้นหา/ตรวจสอบ อ่านอย่างเดียว)'

    # ==================================================================
    # ปี และงวดบัญชี
    # ==================================================================
    @api.model
    def _company(self):
        return self.env.company

    @api.model
    def fiscal_window(self, year):
        u"""คืน (วันเริ่มงวด, วันสิ้นงวด) ของ "ปีบัญชี" ที่จบในปีนั้น

        ไม่ได้ยึด 1 ม.ค.–31 ธ.ค. ตายตัว แต่ยึดวันสิ้นรอบบัญชีที่ตั้งไว้ในบริษัท
        และเผื่อกรณีมีระเบียน account.fiscal.year ที่กำหนดช่วงเองไว้แล้ว
        """
        company = self._company()
        last_month = int(company.fiscalyear_last_month or 12)
        last_day = int(company.fiscalyear_last_day or 31)
        # กันวันที่ไม่มีจริง เช่น ตั้งไว้ 31 แต่เดือนกุมภาพันธ์
        last_day = min(last_day, calendar.monthrange(year, last_month)[1])
        anchor = date(year, last_month, last_day)
        try:
            window = company.compute_fiscalyear_dates(anchor)
            return window['date_from'], window['date_to']
        except Exception:  # noqa: BLE001 - ฐานไหนไม่มีเมธอดนี้ให้คำนวณเอง
            _logger.debug(u'ช่วยปิดงบ: compute_fiscalyear_dates ใช้ไม่ได้ คำนวณงวดเอง')
        if (last_month, last_day) == (12, 31):
            return date(year, 1, 1), date(year, 12, 31)
        start_year = year - 1
        start_month = last_month + 1
        if start_month > 12:
            start_month, start_year = 1, year
        return date(start_year, start_month, 1), anchor

    @api.model
    def available_years(self):
        u"""ปีที่มีรายการลงบันทึกอยู่จริง (ใหม่ไปเก่า) ใช้ตอบ "แต่ละปี" """
        company = self._company()
        self.env.cr.execute(
            """SELECT DISTINCT EXTRACT(YEAR FROM date)::int AS y
                 FROM account_move
                WHERE company_id = %s AND state = 'posted' AND date IS NOT NULL
                ORDER BY y DESC""", (company.id,))
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def parse_years(self, text):
        u"""อ่านปีจากข้อความ รองรับ พ.ศ. (2569) / ค.ศ. (2026) / "ปีนี้" / "ปีที่แล้ว"

        คืน list ของปี ค.ศ. เรียงจากน้อยไปมาก (ว่าง = ไม่ได้ระบุปี)
        """
        text = text or u''
        years = []
        for raw in re.findall(r'\b(\d{4})\b', text):
            value = int(raw)
            if 2500 <= value <= 2600:       # พ.ศ.
                value -= 543
            if 2000 <= value <= 2100:
                years.append(value)
        today = date.today()
        if not years:
            if u'ปีที่แล้ว' in text or u'ปีก่อน' in text or u'ปีที่ผ่านมา' in text:
                years.append(today.year - 1)
            elif u'ปีนี้' in text or u'ปีปัจจุบัน' in text:
                years.append(today.year)
        # "ทุกปี" / "แต่ละปี" -> เอาปีที่มีข้อมูลจริงมาให้หมด
        if not years and (u'ทุกปี' in text or u'แต่ละปี' in text or u'ทุกๆปี' in text):
            years = sorted(self.available_years())[-MAX_YEARS:]
        return sorted(set(years))[:MAX_YEARS]

    @api.model
    def default_year(self):
        u"""ปีที่น่าจะกำลังจะปิด: ปีล่าสุดที่มีรายการ (ถ้าไม่มีเลยใช้ปีปัจจุบัน)"""
        years = self.available_years()
        return years[0] if years else date.today().year

    # ==================================================================
    # ค้นเมนูจริงในฐานนี้
    # ==================================================================
    @api.model
    def find_menus(self, keyword, limit=4, hint=None):
        u"""ค้นเมนูจาก ir.ui.menu ของฐานนี้จริง ๆ

        คืน [{'path': เส้นทางเต็ม, 'visible': ผู้ใช้คนนี้เห็นเมนูนี้ไหม}]

        สองเรื่องที่ต้องระวัง (เจอจริงตอนทดสอบ)
        1) ir.ui.menu.search() กรองเมนูที่ "ผู้ใช้ปัจจุบันมองไม่เห็น" ทิ้งไปเลย
           ต้องใส่ context 'ir.ui.menu.full_list' ก่อน ไม่งั้นเมนูอย่าง
           Trial Balance จะค้นไม่เจอ ทั้งที่มีอยู่ในระบบ -- ซึ่งเป็นเคสที่เรา
           อยากตอบมากที่สุด (บัญชีหาเมนูไม่เจอเพราะสิทธิ์ไม่พอ)
        2) ชื่อเมนูซ้ำกันหลายที่ (Journals มีทั้งใต้ Accounting และใต้
           Configuration) จึงต้องให้คะแนนโดยเทียบกับเส้นทางที่คู่มือระบุไว้
           ไม่งั้นจะแนะนำเมนูผิดตัว
        """
        keyword = (keyword or u'').strip()
        if not keyword:
            return []
        Menu = self.env['ir.ui.menu']
        # ชื่อเมนูเป็นฟิลด์แปลภาษา การค้นจะค้นเฉพาะภาษาที่ผู้ใช้เปิดอยู่
        # พนักงานเปิดหน้าจอภาษาไทย แต่ชื่อเมนูจริงหลายตัวเป็นอังกฤษ
        # (Trial Balance) ถ้าค้นภาษาเดียวจะไม่เจอ ต้องค้นทั้งสองภาษาแล้วรวมกัน
        base = Menu.sudo().with_context(**{'ir.ui.menu.full_list': True})
        candidates = base.browse()
        for lang in (self.env.lang or 'en_US', 'en_US'):
            try:
                found = base.with_context(lang=lang).search(
                    [('name', 'ilike', keyword)], limit=60)
            except Exception:  # noqa: BLE001
                continue
            candidates |= found.with_env(base.env)
        if not candidates:
            return []
        visible_ids = set(Menu.search([('id', 'in', candidates.ids)]).ids)

        hint_parts = []
        for part in re.split(r'[>/]', hint or u''):
            part = part.strip().lower()
            if part and part not in hint_parts:
                hint_parts.append(part)
        # เส้นทางที่คู่มือระบุ เขียนให้อยู่รูปเดียวกับ complete_name เพื่อเทียบตรง ๆ
        hint_path = u'/'.join(part.strip().lower()
                              for part in re.split(r'[>/]', hint or u'') if part.strip())
        keyword_lower = keyword.lower()

        scored = []
        seen = set()
        for menu in candidates:
            try:
                path = menu.complete_name
            except Exception:  # noqa: BLE001 - เมนูกำพร้าบางตัวคำนวณ path ไม่ได้
                path = menu.name
            if not path or path in seen:
                continue
            # เมนูที่ระบบซ่อนไว้ (Hide Menu) ไม่ใช่ทางที่ควรแนะนำให้คนไปกด
            if u'hide menu' in path.lower():
                continue
            seen.add(path)
            path_lower = path.lower()
            score = 0
            # ตรงกับเส้นทางที่คู่มือระบุเป๊ะ = ตัวที่ต้องการแน่นอน ต้องชนะขาด
            # (ชื่อเมนูซ้ำกันหลายที่ ถ้าให้คะแนนแบบนับคำจะพลิกกันด้วยคะแนนแต้มเดียว)
            if hint_path and path_lower == hint_path:
                score += 500
            if (menu.name or u'').strip().lower() == keyword_lower:
                score += 100
            elif path_lower.split('/')[-1].startswith(keyword_lower):
                score += 40
            for part in hint_parts:
                if part in path_lower:
                    score += 10
            score -= path.count('/')          # ยิ่งลึกยิ่งไม่น่าใช่ตัวที่ต้องการ
            if menu.id in visible_ids:
                score += 2                    # เสมอกันให้เลือกอันที่กดได้จริง
            scored.append((score, path, menu.id in visible_ids))

        scored.sort(key=lambda row: (-row[0], len(row[1])))
        return [{'path': path, 'visible': visible} for _score, path, visible in scored[:limit]]

    @api.model
    def _item_menu_text(self, item):
        u"""เส้นทางเมนูของรายการหนึ่งในคู่มือ -- เอาของจริงในฐานก่อน"""
        hint = item.get('path') or u''
        found = self.find_menus(item.get('find') or u'', limit=1, hint=hint)
        if found:
            note = u'' if found[0]['visible'] else u' (สิทธิ์ของคุณยังไม่เห็นเมนูนี้)'
            return found[0]['path'] + note
        return hint

    # ==================================================================
    # ตัวตรวจ -- "ติดที่รายการไหน" และ "เท่าไหร่ถึงจะถูก"
    # ==================================================================
    def _blank(self, key, title, menu_find, menu_path):
        return {
            'key': key, 'title': title, 'status': 'ok',
            'found': u'', 'need': u'', 'fix': u'',
            'menu_find': menu_find, 'menu_path': menu_path,
            'amount': 0.0, 'count': 0,
            'columns': [], 'rows': [],
        }

    def _check_draft_moves(self, year, dfrom, dto):
        check = self._blank('draft_moves', u'ใบค้างร่างในปี',
                            u'Journal Entries',
                            u'Accounting > Accounting > Miscellaneous > Journal Entries')
        Move = self.env['account.move'].sudo()
        domain = [('company_id', '=', self._company().id),
                  ('date', '>=', dfrom), ('date', '<=', dto),
                  ('state', '=', 'draft')]
        count = Move.search_count(domain)
        check['count'] = count
        if not count:
            check['found'] = u'ไม่มีใบค้างร่าง'
            check['need'] = u'—'
            return check
        check['status'] = 'block'
        groups = Move.read_group(domain, [], ['journal_id'], lazy=False)
        parts = [u'%s %s ใบ' % (g['journal_id'][1] if g.get('journal_id') else u'ไม่ระบุ',
                                g['__count'])
                 for g in sorted(groups, key=lambda g: -g['__count'])[:6]]
        check['found'] = u'ค้าง %s ใบ (%s)' % ('{:,}'.format(count), u' · '.join(parts))
        check['need'] = u'ต้องเหลือ 0 ใบ — ยังเหลืออีก %s ใบ' % '{:,}'.format(count)
        check['fix'] = u'กรอง Draft + ปี %s แล้วไล่กด Post ถ้ารายการถูก หรือ Cancel ถ้าไม่ใช้' % year
        check['columns'] = [(u'เลขที่', 'name'), (u'วันที่', 'date'),
                            (u'สมุดรายวัน', 'journal_id'), (u'คู่ค้า', 'partner_id'),
                            (u'ยอดรวม', 'amount_total')]
        check['rows'] = Move.search_read(domain, ['name', 'date', 'journal_id',
                                                  'partner_id', 'amount_total'],
                                         limit=MAX_EXCEL_ROWS, order='date, name')
        return check

    def _check_balance(self, year, dfrom, dto):
        check = self._blank('trial_balance', u'งบทดลองสมดุล (เดบิต = เครดิต)',
                            u'Trial Balance',
                            u'Accounting > Reporting > Dynamic Reports(Wiz) > Trial Balance')
        self.env.cr.execute(
            """SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
                 FROM account_move_line
                WHERE company_id = %s AND parent_state = 'posted'
                  AND date >= %s AND date <= %s""",
            (self._company().id, dfrom, dto))
        debit, credit = self.env.cr.fetchone()
        diff = float(debit) - float(credit)
        check['amount'] = abs(diff)
        if abs(diff) < EPS:
            check['found'] = u'เดบิต = เครดิต = %s บาท' % _money(debit)
            check['need'] = u'—'
            return check
        check['status'] = 'block'
        check['found'] = u'เดบิต %s / เครดิต %s' % (_money(debit), _money(credit))
        check['need'] = u'ต่างกัน %s บาท ต้องเป็น 0' % _money(abs(diff))
        check['fix'] = u'เปิดงบทดลองช่วง %s ถึง %s แล้วไล่หาบัญชีที่ทำให้ไม่สมดุล' % (
            _thai_date(dfrom), _thai_date(dto))
        return check

    def _check_unreconciled(self, year, dfrom, dto):
        check = self._blank('unreconciled', u'ลูกหนี้-เจ้าหนี้ที่ยังไม่กระทบยอด',
                            u'Reconciliation',
                            u'Accounting > Accounting > Actions > Reconciliation')
        Line = self.env['account.move.line'].sudo()
        # account_internal_type ในฐานนี้ไม่ได้ store จึงต้องไล่ผ่านความสัมพันธ์
        domain = [('company_id', '=', self._company().id),
                  ('parent_state', '=', 'posted'),
                  ('date', '<=', dto),
                  ('reconciled', '=', False),
                  ('account_id.user_type_id.type', 'in', ('receivable', 'payable'))]
        count = Line.search_count(domain)
        if not count:
            check['found'] = u'กระทบยอดครบแล้ว'
            check['need'] = u'—'
            return check
        # read_group ของ Odoo 14 จัดกลุ่มด้วยฟิลด์แบบจุด (a.b.c) ไม่ได้
        # ยอดคงเหลือฝั่งลูกหนี้เป็นบวก ฝั่งเจ้าหนี้เป็นลบ ถ้ารวมตรง ๆ จะหักล้างกัน
        # จึงต้องรวมค่าสัมบูรณ์ด้วย SQL แทน (อ่านอย่างเดียวเหมือนเดิม)
        self.env.cr.execute(
            """SELECT COALESCE(SUM(ABS(l.amount_residual)), 0)
                 FROM account_move_line l
                 JOIN account_account a ON a.id = l.account_id
                 JOIN account_account_type t ON t.id = a.user_type_id
                WHERE l.company_id = %s AND l.parent_state = 'posted'
                  AND l.date <= %s AND l.reconciled = FALSE
                  AND t.type IN ('receivable', 'payable')""",
            (self._company().id, dto))
        total = float((self.env.cr.fetchone() or [0.0])[0] or 0.0)
        check['count'] = count
        check['amount'] = total
        check['status'] = 'warn'
        check['found'] = u'ค้าง %s บรรทัด ยอดคงเหลือรวม %s บาท' % (
            '{:,}'.format(count), _money(total))
        check['need'] = (u'ไม่จำเป็นต้องเป็น 0 — ที่เหลือต้องเป็นหนี้ที่ยังค้างชำระจริง '
                         u'ณ %s เท่านั้น' % _thai_date(dto))
        check['fix'] = u'จับคู่ใบแจ้งหนี้กับการรับ/จ่ายชำระที่ค้าง แล้วสอบยอดกับรายงานอายุหนี้'
        check['columns'] = [(u'วันที่', 'date'), (u'เลขที่', 'move_name'),
                            (u'คู่ค้า', 'partner_id'), (u'บัญชี', 'account_id'),
                            (u'คงเหลือ', 'amount_residual')]
        check['rows'] = Line.search_read(
            domain, ['date', 'move_name', 'partner_id', 'account_id', 'amount_residual'],
            limit=MAX_EXCEL_ROWS, order='date desc')
        return check

    def _check_assets(self, year, dfrom, dto):
        check = self._blank('assets', u'ค่าเสื่อมราคา', u'Assets', u'Accounting > Assets')
        if 'account.asset' not in self.env:
            check['status'] = 'skip'
            check['found'] = u'ฐานนี้ไม่ได้ติดตั้งโมดูลสินทรัพย์'
            return check
        Asset = self.env['account.asset'].sudo()
        company_id = self._company().id
        draft = Asset.search_count([('company_id', '=', company_id), ('state', '=', 'draft')])
        pending, pending_amount = 0, 0.0
        if 'account.asset.line' in self.env:
            Line = self.env['account.asset.line'].sudo()
            line_domain = [('asset_id.company_id', '=', company_id),
                           ('type', '=', 'depreciate'),
                           ('init_entry', '=', False),
                           ('move_check', '=', False),
                           ('line_date', '>=', dfrom), ('line_date', '<=', dto)]
            pending = Line.search_count(line_domain)
            if pending:
                groups = Line.read_group(line_domain, ['amount'], [], lazy=False)
                pending_amount = (groups[0].get('amount') if groups else 0.0) or 0.0
                check['columns'] = [(u'สินทรัพย์', 'asset_id'), (u'งวดวันที่', 'line_date'),
                                    (u'ค่าเสื่อม', 'amount')]
                check['rows'] = Line.search_read(line_domain,
                                                 ['asset_id', 'line_date', 'amount'],
                                                 limit=MAX_EXCEL_ROWS, order='line_date')
        check['count'] = draft + pending
        check['amount'] = pending_amount
        if not draft and not pending:
            check['found'] = u'ค่าเสื่อมลงครบถึงสิ้นปีแล้ว'
            check['need'] = u'—'
            return check
        check['status'] = 'block' if pending else 'warn'
        found = []
        need = []
        if draft:
            found.append(u'สินทรัพย์สถานะร่าง %s รายการ' % '{:,}'.format(draft))
            need.append(u'ต้องยืนยันให้ครบอีก %s รายการ' % '{:,}'.format(draft))
        if pending:
            found.append(u'งวดค่าเสื่อมที่ยังไม่ลงบัญชี %s งวด' % '{:,}'.format(pending))
            need.append(u'ยังขาดค่าเสื่อมอีก %s บาท' % _money(pending_amount))
        check['found'] = u' · '.join(found)
        check['need'] = u' · '.join(need)
        check['fix'] = (u'ยืนยันสินทรัพย์ที่ยังเป็นร่าง แล้วสั่ง Compute Assets '
                        u'ให้สร้างใบค่าเสื่อม จากนั้น Post ใบ JE ค่าเสื่อม')
        return check

    def _check_fiscal_year(self, year, dfrom, dto):
        check = self._blank('fiscal_year', u'ปีบัญชีในระบบ', u'Fiscal Years',
                            u'Accounting > Configuration > Accounting > Fiscal Years')
        if 'account.fiscal.year' not in self.env:
            check['status'] = 'skip'
            check['found'] = u'ฐานนี้ไม่มีเมนูปีบัญชี'
            return check
        record = self.env['account.fiscal.year'].sudo().search(
            [('company_id', '=', self._company().id),
             ('date_from', '<=', dto), ('date_to', '>=', dfrom)], limit=1)
        if record:
            check['found'] = u'%s (%s – %s)' % (record.name, _thai_date(record.date_from),
                                                _thai_date(record.date_to))
            check['need'] = u'—'
            return check
        check['status'] = 'warn'
        check['found'] = u'ยังไม่มีปีบัญชีของปี %s' % year
        check['need'] = u'สร้าง 1 ระเบียน: %s ถึง %s' % (_thai_date(dfrom), _thai_date(dto))
        check['fix'] = u'กดสร้าง แล้วใส่ชื่อปี วันเริ่ม วันสิ้นสุด และบริษัท'
        return check

    def _check_closing_template(self, year, dfrom, dto):
        check = self._blank('closing_template', u'แม่แบบใบปิดบัญชี', u'Fiscal Year Closing',
                            u'Accounting > Configuration > Fiscal Year Closing > Closing templates')
        if 'account.fiscalyear.closing.template' not in self.env:
            check['status'] = 'skip'
            check['found'] = u'ฐานนี้ไม่ได้ติดตั้งโมดูลปิดงบ'
            return check
        templates = self.env['account.fiscalyear.closing.template'].sudo().search([])
        if not templates:
            check['status'] = 'block'
            check['found'] = u'ยังไม่มีแม่แบบใบปิดบัญชีเลย'
            check['need'] = u'ต้องมีอย่างน้อย 1 แม่แบบ ที่มี Account mappings'
            check['fix'] = (u'สร้างแม่แบบ แล้วใส่บรรทัด Loss & Profit '
                            u'Source 4%,5%,6% -> Destination บัญชีกำไร(ขาดทุน)')
            return check
        # แม่แบบที่ไม่มี mapping = กด Calculate แล้วระบบเงียบ ไม่สร้างอะไรเลย
        usable = []
        for template in templates:
            has_mapping = any(config.mapping_ids for config in template.move_config_ids)
            if has_mapping:
                usable.append(template.name or u'(ไม่มีชื่อ)')
        if usable:
            check['found'] = u'ใช้ได้ %s แม่แบบ (%s)' % (len(usable), u' · '.join(usable[:3]))
            check['need'] = u'—'
            return check
        check['status'] = 'block'
        check['found'] = u'มี %s แม่แบบ แต่ยังไม่ได้ใส่ Account mappings เลย' % len(templates)
        check['need'] = u'ต้องใส่ mapping อย่างน้อย 1 บรรทัด'
        check['fix'] = (u'ถ้าไม่ใส่ mapping ตอนกด Calculate ระบบจะเงียบ ไม่สร้างรายการ '
                        u'และไม่ขึ้น error ด้วย')
        return check

    def _check_closing_entry(self, year, dfrom, dto):
        check = self._blank('closing_entry', u'ใบปิดบัญชีของปีนี้', u'Fiscal year closings',
                            u'Accounting > Accounting > Fiscal year closings')
        if 'account.fiscalyear.closing' not in self.env:
            check['status'] = 'skip'
            check['found'] = u'ฐานนี้ไม่ได้ติดตั้งโมดูลปิดงบ'
            return check
        Closing = self.env['account.fiscalyear.closing'].sudo()
        record = Closing.search([('company_id', '=', self._company().id),
                                 ('year', '=', year)], limit=1)
        if not record:
            check['status'] = 'block'
            check['found'] = u'ยังไม่ได้สร้างใบปิดบัญชีของปี %s' % year
            check['need'] = u'ต้องมี 1 ใบ และสถานะต้องเป็น Posted'
            check['fix'] = u'กดสร้าง ใส่ Year = %s เลือกแม่แบบ แล้วกด Calculate ก่อน Post' % year
            return check
        state = record.state or u''
        labels = dict(Closing._fields['state'].selection or [])
        check['found'] = u'%s — สถานะ %s' % (record.name or record.year,
                                             labels.get(state, state))
        if state == 'posted':
            check['need'] = u'—'
            return check
        check['status'] = 'block'
        check['need'] = u'ต้องกด Post ให้สถานะเป็น Posted'
        check['fix'] = (u'กด Calculate แล้วเปิดปุ่ม Moves ตรวจตัวเลขกับงบที่พิมพ์ไว้ '
                        u'ถ้าตรงจึงกด Post (ก่อน Post ยังถอยกลับได้)')
        return check

    def _check_closing_amount(self, year, dfrom, dto):
        u"""ยอดที่ใบปิดโอนเข้าบัญชีทุน ตรงกับกำไรในงบกำไรขาดทุนไหม

        เจอจากการทดสอบจริง: แม่แบบจับบัญชีด้วย "รหัสขึ้นต้น" (4% 5% 6%)
        แต่งบกำไรขาดทุนจัดกลุ่มด้วย "ประเภทบัญชี" สองอย่างนี้ไม่เท่ากันเสมอไป
        (บัญชีพัก 9999-99 เป็นค่าใช้จ่ายแต่รหัสขึ้นต้น 9 จึงไม่ถูกล้าง
         และถ้ายังมีใบค้างร่าง ยอดที่คำนวณได้ก็จะเพี้ยนไปอีก)
        ต่างกันเมื่อไรต้องให้บัญชีตรวจก่อน Post ห้ามปล่อยผ่าน
        """
        check = self._blank('closing_amount', u'ยอดในใบปิดตรงกับงบไหม',
                            u'Fiscal year closings',
                            u'Accounting > Accounting > Fiscal year closings')
        if 'account.fiscalyear.closing' not in self.env:
            check['status'] = 'skip'
            check['found'] = u'ฐานนี้ไม่ได้ติดตั้งโมดูลใบปิดบัญชี'
            return check
        closing = self.env['account.fiscalyear.closing'].sudo().search(
            [('company_id', '=', self._company().id), ('year', '=', year)], limit=1)
        moves = closing.move_ids if closing else self.env['account.move']
        if not moves:
            check['status'] = 'skip'
            check['found'] = u'ยังไม่ได้สร้างใบปิด จึงยังไม่มีตัวเลขให้เทียบ'
            check['need'] = u'ตรวจข้อนี้ได้หลังกด Calculate'
            return check

        move_ids = tuple(moves.ids)
        # กำไรของปี โดยไม่นับใบปิดเอง
        self.env.cr.execute(
            """SELECT COALESCE(SUM(l.balance), 0)
                 FROM account_move_line l
                 JOIN account_account a ON a.id = l.account_id
                 JOIN account_account_type t ON t.id = a.user_type_id
                WHERE l.company_id = %s AND l.parent_state = 'posted'
                  AND l.date >= %s AND l.date <= %s
                  AND t.internal_group IN ('income', 'expense')
                  AND l.move_id NOT IN %s""",
            (self._company().id, dfrom, dto, move_ids))
        profit = -float((self.env.cr.fetchone() or [0.0])[0] or 0.0)
        # ยอดที่ใบปิดโอนออกไปฝั่งทุน/งบดุล (ไม่ใช่บัญชีรายได้-ค่าใช้จ่าย)
        self.env.cr.execute(
            """SELECT COALESCE(SUM(l.balance), 0)
                 FROM account_move_line l
                 JOIN account_account a ON a.id = l.account_id
                 JOIN account_account_type t ON t.id = a.user_type_id
                WHERE l.move_id IN %s
                  AND t.internal_group NOT IN ('income', 'expense')""",
            (move_ids,))
        transferred = -float((self.env.cr.fetchone() or [0.0])[0] or 0.0)
        diff = transferred - profit
        check['amount'] = abs(diff)
        check['found'] = u'ใบปิดโอน %s · กำไรตามงบ %s' % (_money(transferred), _money(profit))
        if abs(diff) < EPS:
            check['need'] = u'—'
            return check
        check['status'] = 'block'
        check['need'] = u'ต่างกัน %s บาท ต้องเป็น 0 ก่อน Post' % _money(abs(diff))
        check['fix'] = (u'สาเหตุที่พบบ่อย: (1) มีบัญชีรายได้/ค่าใช้จ่ายที่รหัสไม่ได้ขึ้นต้น '
                        u'4/5/6 เช่นบัญชีพัก จึงไม่ถูกล้าง (2) ยังมีใบค้างร่างในปี '
                        u'ทำให้ยอดที่คำนวณเพี้ยน — เคลียร์ใบร่างแล้วกด Recalculate ใหม่')
        return check

    def _check_lock_dates(self, year, dfrom, dto):
        check = self._blank('lock_dates', u'การล็อกวันที่', u'lock dates',
                            u'Accounting > Accounting > Actions > Update accounting lock dates')
        company = self._company()
        period = company.period_lock_date
        fiscal = company.fiscalyear_lock_date
        tax = company.tax_lock_date
        check['found'] = u'ทั่วไป %s · ทุกคน %s · ภาษี %s' % (
            _thai_date(period), _thai_date(fiscal), _thai_date(tax))
        if fiscal and fiscal >= dto:
            check['need'] = u'—'
            return check
        check['status'] = 'warn'
        check['need'] = u'หลังปิดงบเสร็จ ให้ตั้ง Lock Date for All Users = %s' % _thai_date(dto)
        check['fix'] = (u'ระหว่างที่ยังปิดไม่เสร็จ ใส่แค่ Lock Date for Non-Advisers ก่อน '
                        u'กันคนอื่นย้อนไปแก้ ส่วน Lock Date for All Users ใส่ตอนปิดเสร็จจริง')
        return check

    def _check_result(self, year, dfrom, dto):
        u"""กำไร(ขาดทุน) ของปี -- ตัวเลขที่ต้องไปโผล่ในใบปิดบัญชี"""
        check = self._blank('pl_result', u'กำไร(ขาดทุน) ของปี', u'Profit and Loss',
                            u'Accounting > Reporting > Dynamic Reports(Wiz) > Profit and Loss')
        self.env.cr.execute(
            """SELECT t.internal_group, COALESCE(SUM(l.balance), 0)
                 FROM account_move_line l
                 JOIN account_account a ON a.id = l.account_id
                 JOIN account_account_type t ON t.id = a.user_type_id
                WHERE l.company_id = %s AND l.parent_state = 'posted'
                  AND l.date >= %s AND l.date <= %s
                  AND t.internal_group IN ('income', 'expense')
                GROUP BY t.internal_group""",
            (self._company().id, dfrom, dto))
        totals = dict(self.env.cr.fetchall())
        income = -float(totals.get('income') or 0.0)     # รายได้เป็นเครดิต -> balance ติดลบ
        expense = float(totals.get('expense') or 0.0)
        profit = income - expense
        check['amount'] = profit
        check['found'] = u'รายได้ %s − ค่าใช้จ่าย %s = %s %s' % (
            _money(income), _money(expense), _money(abs(profit)),
            u'กำไร' if profit >= 0 else u'ขาดทุน')
        check['need'] = u'ตัวเลขนี้ต้องตรงกับใบปิดบัญชีที่ระบบสร้างให้'
        check['fix'] = u'พิมพ์งบกำไรขาดทุนเก็บไว้ก่อนกด Post ใบปิดบัญชี'
        return check

    def _check_unaffected_earnings(self, year, dfrom, dto):
        u"""ยอดคงค้างในบัญชี "กำไร(ขาดทุน) ปีปัจจุบัน" ณ สิ้นปี

        ถ้าปิดงบแล้วจริง ยอดของปีนั้นควรถูกโอนออกไปกำไรสะสมแล้ว
        """
        check = self._blank('unaffected', u'บัญชีกำไร(ขาดทุน) ปีปัจจุบัน', u'General Ledger',
                            u'Accounting > Reporting > Dynamic Reports(Wiz) > General Ledger')
        self.env.cr.execute(
            """SELECT COALESCE(SUM(l.balance), 0)
                 FROM account_move_line l
                 JOIN account_account a ON a.id = l.account_id
                 JOIN account_account_type t ON t.id = a.user_type_id
                WHERE l.company_id = %s AND l.parent_state = 'posted'
                  AND l.date <= %s AND t.type = 'other'
                  AND t.internal_group = 'equity'
                  AND t.include_initial_balance IS TRUE
                  AND LOWER(t.name) LIKE %s""",
            (self._company().id, dto, '%current year%'))
        row = self.env.cr.fetchone()
        balance = float((row or [0.0])[0] or 0.0)
        check['amount'] = abs(balance)
        check['found'] = u'ยอดสะสม ณ %s = %s บาท' % (_thai_date(dto), _money(-balance))
        check['need'] = u'เป็นตัวชี้ว่าเคยโอนกำไรเข้ากำไรสะสมแล้วหรือยัง'
        check['fix'] = u'ถ้าไม่เคยปิดงบเลย บัญชีนี้จะยังไม่มีรายการ'
        return check

    def _check_month_gaps(self, year, dfrom, dto):
        check = self._blank('month_gaps', u'เดือนที่ไม่มีรายการเลย', u'Journal Entries',
                            u'Accounting > Accounting > Miscellaneous > Journal Entries')
        self.env.cr.execute(
            """SELECT DISTINCT EXTRACT(MONTH FROM date)::int
                 FROM account_move
                WHERE company_id = %s AND state = 'posted'
                  AND date >= %s AND date <= %s""",
            (self._company().id, dfrom, dto))
        have = {row[0] for row in self.env.cr.fetchall()}
        # นับเฉพาะเดือนที่อยู่ในงวดและผ่านมาแล้วจริง (ปีปัจจุบันยังไม่ครบปี)
        today = date.today()
        months = []
        cursor = date(dfrom.year, dfrom.month, 1)
        while cursor <= dto:
            if cursor <= today:
                months.append(cursor.month)
            if cursor.month == 12:
                cursor = date(cursor.year + 1, 1, 1)
            else:
                cursor = date(cursor.year, cursor.month + 1, 1)
        missing = [m for m in months if m not in have]
        if not missing:
            check['found'] = u'มีรายการครบทุกเดือน'
            check['need'] = u'—'
            return check
        check['status'] = 'warn'
        check['count'] = len(missing)
        check['found'] = u'เดือน %s ไม่มีรายการลงบันทึกเลย' % u', '.join(str(m) for m in missing)
        check['need'] = u'ยืนยันว่าเดือนนั้นไม่มีรายการจริง ไม่ใช่ลืมลง'
        check['fix'] = u'ถ้าเป็นเดือนที่ยังไม่ได้เปิดใช้ระบบ ถือว่าปกติ'
        return check

    @api.model
    def run_checks(self, year):
        u"""รันตัวตรวจทั้งหมดของปีนั้น (อ่านอย่างเดียว) คืน list ของผลตรวจ

        ตัวตรวจตัวไหนพังไม่ควรทำให้ทั้งหัวข้อพัง -- ฐานแต่ละบริษัทติดตั้งโมดูล
        ไม่เท่ากัน จึงห่อ try ทีละตัวแล้วรายงานว่าตรวจไม่ได้แทน
        """
        dfrom, dto = self.fiscal_window(year)
        checkers = [
            self._check_draft_moves, self._check_balance, self._check_unreconciled,
            self._check_assets, self._check_month_gaps, self._check_result,
            self._check_fiscal_year, self._check_closing_template,
            self._check_closing_entry, self._check_closing_amount,
            self._check_unaffected_earnings, self._check_lock_dates,
        ]
        results = []
        for checker in checkers:
            try:
                results.append(checker(year, dfrom, dto))
            except Exception as exc:  # noqa: BLE001
                _logger.warning(u'ช่วยปิดงบ: ตัวตรวจ %s ของปี %s ล้ม (%s)',
                                checker.__name__, year, exc)
                broken = self._blank(checker.__name__, checker.__name__, u'', u'')
                broken['status'] = 'skip'
                broken['found'] = u'ตรวจรายการนี้ไม่สำเร็จ'
                results.append(broken)
        return results

    @api.model
    def verdict(self, year, checks=None):
        u"""ฟันธงว่าปีนั้น "ปิดงบสมบูรณ์แล้วหรือยัง" พร้อมรายการที่ติด"""
        checks = checks if checks is not None else self.run_checks(year)
        blocking = [c for c in checks if c['status'] == 'block']
        warnings = [c for c in checks if c['status'] == 'warn']
        posted = any(c['key'] == 'closing_entry' and c['status'] == 'ok' for c in checks)
        dfrom, dto = self.fiscal_window(year)
        return {
            'year': year,
            'date_from': dfrom,
            'date_to': dto,
            'complete': bool(posted and not blocking),
            'blocking': blocking,
            'warnings': warnings,
            'checks': checks,
        }

    # ==================================================================
    # จัดรูปคำตอบสำหรับแชท
    # ==================================================================
    @api.model
    def steps_blocks(self):
        u"""แผนที่เมนู 4 ขั้น -- ย่อให้อ่านจบในจอเดียว"""
        blocks = [u'<b>ปิดงบใน Odoo มี 4 ขั้น เรียงกันเสมอ ห้ามสลับ</b>']
        rows = [u'<tr><th style="text-align:left">ขั้น</th>'
                u'<th style="text-align:left">ทำอะไร</th>'
                u'<th style="text-align:left">ทำไมต้องลำดับนี้</th></tr>']
        for step in CLOSING_STEPS:
            rows.append(u'<tr><td>%s</td><td><b>%s</b></td><td>%s</td></tr>' % (
                step['order'], html_escape(step['title']), html_escape(step['why'])))
        blocks.append(u'<table class="table table-sm" style="width:100%%">%s</table>'
                      % u''.join(rows))
        blocks.append(u'<span class="text-muted">พิมพ์ "ขั้นที่ 1" ถึง "ขั้นที่ 4" '
                      u'เพื่อดูเมนูของแต่ละขั้น</span>')
        return blocks

    @api.model
    def step_detail_blocks(self, order):
        step = next((s for s in CLOSING_STEPS if s['order'] == order), None)
        if not step:
            return []
        blocks = [u'<b>ขั้นที่ %s — %s</b><br/><span class="text-muted">%s</span>'
                  % (step['order'], html_escape(step['title']), html_escape(step['goal']))]
        rows = [u'<tr><th style="text-align:left">ทำอะไร</th>'
                u'<th style="text-align:left">เมนู</th>'
                u'<th style="text-align:left">ผ่านเมื่อไร</th></tr>']
        for item in step['items']:
            rows.append(u'<tr><td><b>%s</b><br/><span class="text-muted">%s</span></td>'
                        u'<td>%s</td><td>%s</td></tr>' % (
                            html_escape(item['name']), html_escape(item['what']),
                            html_escape(self._item_menu_text(item)),
                            html_escape(item['pass'])))
        blocks.append(u'<table class="table table-sm" style="width:100%%">%s</table>'
                      % u''.join(rows))
        return blocks

    @api.model
    def verdict_line(self, year, checks=None, verdict=None):
        u"""บรรทัดฟันธงสั้น ๆ ต่อท้ายทุกคำตอบ

        ผู้ใช้สั่งว่า "ถาม AI เสร็จแล้วให้ตรวจด้วยว่าปิดงบสมบูรณ์หรือไม่"
        ทุกคำตอบจึงต้องปิดท้ายด้วยข้อสรุปนี้เสมอ ไม่ว่าจะถามเรื่องอะไร
        """
        verdict = verdict or self.verdict(year, checks=checks)
        if verdict['complete']:
            text = u'<b>🟢 สรุป: ปี %s ปิดงบสมบูรณ์แล้ว</b>' % year
            if verdict['warnings']:
                text += u'<br/><span class="text-muted">ยังมีเรื่องที่ควรดูอีก %s รายการ</span>' \
                        % len(verdict['warnings'])
            return text
        titles = u' · '.join(c['title'] for c in verdict['blocking'][:5])
        return (u'<b>🔴 สรุป: ปี %s ยังปิดงบไม่สมบูรณ์ — ติด %s เรื่อง</b>'
                u'<br/><span class="text-muted">%s</span>'
                u'<br/><span class="text-muted">พิมพ์ "ตรวจปี %s" '
                u'เพื่อดูว่าต้องแก้เท่าไหร่และทำที่เมนูไหน</span>'
                % (year, len(verdict['blocking']), html_escape(titles), year))

    @api.model
    def checks_blocks(self, year, checks=None, verdict=None):
        u"""ผลตรวจของปีหนึ่ง: ฟันธงก่อน แล้วค่อยลงรายการ"""
        checks = checks if checks is not None else self.run_checks(year)
        verdict = verdict or self.verdict(year, checks=checks)
        blocks = []
        if verdict['complete']:
            head = (u'<b>🟢 ปี %s ปิดงบสมบูรณ์แล้ว</b>' % year)
            if verdict['warnings']:
                head += u'<br/>เหลือเรื่องที่ควรดู %s รายการ' % len(verdict['warnings'])
        else:
            head = (u'<b>🔴 ปี %s ยังปิดงบไม่สมบูรณ์</b><br/>ติด <b>%s เรื่อง</b>'
                    % (year, len(verdict['blocking'])))
            if verdict['warnings']:
                head += u' · ควรดูอีก %s เรื่อง' % len(verdict['warnings'])
        head += (u'<br/><span class="text-muted">งวด %s ถึง %s</span>'
                 % (_thai_date(verdict['date_from']), _thai_date(verdict['date_to'])))
        blocks.append(head)

        rows = [u'<tr><th style="text-align:left">รายการ</th>'
                u'<th style="text-align:left">ที่พบ</th>'
                u'<th style="text-align:left">เท่าไหร่ถึงจะถูก</th></tr>']
        for check in checks:
            rows.append(u'<tr><td>%s <b>%s</b></td><td>%s</td><td>%s</td></tr>' % (
                STATUS_ICON.get(check['status'], u''), html_escape(check['title']),
                html_escape(check['found'] or u'—'), html_escape(check['need'] or u'—')))
        blocks.append(u'<table class="table table-sm" style="width:100%%">%s</table>'
                      % u''.join(rows))

        if verdict['blocking']:
            fixes = []
            for check in verdict['blocking']:
                fixes.append(u'<div class="mb-1"><b>%s</b><br/>%s<br/>'
                             u'<span class="text-muted">เมนู: %s</span></div>' % (
                                 html_escape(check['title']),
                                 html_escape(check['fix'] or check['need'] or u''),
                                 html_escape(self._item_menu_text(
                                     {'find': check['menu_find'], 'path': check['menu_path']}))))
            blocks.append(u'<b>วิธีแก้ เรียงตามลำดับที่ควรทำ</b>%s' % u''.join(fixes))
        blocks += self.verify_blocks(year)
        return blocks

    @api.model
    def verify_blocks(self, year):
        u"""บอกว่าให้บัญชีไปตรวจซ้ำที่เมนูไหน และถอยกลับยังไงถ้าทำผิด

        ผู้ใช้สั่งว่าทุกครั้งที่ AI รายงานผล ต้องบอกทางตรวจซ้ำและทางถอยกลับด้วย
        เพื่อกันพลาด ไม่ใช่ให้เชื่อ AI อย่างเดียว
        """
        checkpoints = [
            (u'งบทดลอง', u'Trial Balance',
             u'Accounting > Reporting > Dynamic Reports(Wiz) > Trial Balance',
             u'เดบิตรวมต้องเท่าเครดิตรวม'),
            (u'งบกำไรขาดทุน', u'Profit and Loss',
             u'Accounting > Reporting > Dynamic Reports(Wiz) > Profit and Loss',
             u'กำไรต้องตรงกับยอดที่ใบปิดโอนเข้าบัญชีทุน'),
            (u'งบดุล', u'Balance Sheet',
             u'Accounting > Reporting > Dynamic Reports(Wiz) > Balance Sheet',
             u'ดูว่ากำไรไปโผล่ในส่วนของผู้ถือหุ้นถูกช่อง'),
            (u'ใบที่ระบบสร้างให้', u'Fiscal year closings',
             u'Accounting > Accounting > Fiscal year closings',
             u'เปิดใบปิด แล้วกดปุ่ม Moves ดูทีละบรรทัดก่อน Post'),
        ]
        rows = [u'<tr><th style="text-align:left">ตรวจอะไร</th>'
                u'<th style="text-align:left">เมนู</th>'
                u'<th style="text-align:left">ดูให้แน่ใจว่า</th></tr>']
        for label, find, path, what in checkpoints:
            rows.append(u'<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>' % (
                html_escape(label),
                html_escape(self._item_menu_text({'find': find, 'path': path})),
                html_escape(what)))
        blocks = [u'<b>ตรวจซ้ำก่อนเชื่อผลนี้ — ปี %s</b>' % year,
                  u'<table class="table table-sm" style="width:100%%">%s</table>'
                  % u''.join(rows)]
        blocks.append(
            u'<b>ถ้าทำผิด ถอยกลับได้</b>'
            u'<div class="ml-3">ยังไม่ Post → กด <b>Recalculate</b> คำนวณใหม่ได้เลย</div>'
            u'<div class="ml-3">Post ไปแล้ว → ต้องกด <b>Cancel (ยกเลิก)</b> '
            u'ระบบจะถอนการกระทบยอดและลบใบปิดออกจากบัญชีให้ ยอดกลับเป็นเหมือนก่อนปิดทุกบาท</div>'
            u'<div class="ml-3"><span class="text-muted">อย่ากด <b>Recover</b> หลัง Post — '
            u'มันเปลี่ยนแค่สถานะเป็นร่าง ใบยังค้างอยู่ในบัญชี ถ้ากด Calculate ต่อจะได้ใบซ้ำสองใบ '
            u'(ทดสอบจริงแล้ว)</span></div>')
        return blocks

    @api.model
    def years_blocks(self, years):
        u"""สรุปหลายปีในตารางเดียว ตอบคำถามแบบ "แต่ละปีปิดครบไหม" """
        rows = [u'<tr><th style="text-align:left">ปี</th>'
                u'<th style="text-align:left">สถานะ</th>'
                u'<th style="text-align:left">ติดที่</th></tr>']
        details = []
        for year in years:
            verdict = self.verdict(year)
            details.append(verdict)
            if verdict['complete']:
                status = u'🟢 ปิดสมบูรณ์'
                blocked = u'—'
            else:
                status = u'🔴 ยังไม่สมบูรณ์'
                blocked = u' · '.join(c['title'] for c in verdict['blocking'][:4]) or u'—'
            rows.append(u'<tr><td>%s (พ.ศ. %s)</td><td>%s</td><td>%s</td></tr>'
                        % (year, year + 543, status, html_escape(blocked)))
        blocks = [u'<b>สรุปสถานะการปิดงบแต่ละปี</b>',
                  u'<table class="table table-sm" style="width:100%%">%s</table>'
                  % u''.join(rows),
                  u'<span class="text-muted">พิมพ์ "ปี 2026" เพื่อดูรายละเอียดทีละปี</span>']
        return blocks, details

    @api.model
    def search_guide(self, keyword):
        u"""หารายการในคู่มือที่ตรงกับคำค้น -- รองรับคำไทย

        เมนูในระบบเป็นภาษาอังกฤษเกือบทั้งหมด แต่บัญชีถามเป็นไทย ("งบทดลอง
        อยู่ไหน") การค้น ir.ui.menu ตรง ๆ จึงไม่เจอ ต้องผ่านคู่มือที่เก็บชื่อไทย
        คู่กับชื่ออังกฤษไว้ให้ก่อน
        """
        keyword = (keyword or u'').strip().lower()
        if len(keyword) < 2:
            return []
        hits = []
        for step in CLOSING_STEPS:
            for item in step['items']:
                haystack = u' '.join([item['name'], item['what'], item['path'],
                                      item['find']]).lower()
                if keyword in haystack:
                    hits.append((step, item))
        return hits

    @api.model
    def menu_blocks(self, keyword):
        u"""ตอบ "เมนูนี้อยู่ไหน เอาไว้ทำอะไร" -- คืน [] ถ้าไม่รู้จริง ๆ

        คืนลิสต์ว่างแทนการตอบ "ไม่พบ" เพื่อให้ผู้เรียกส่งต่อให้ AI ตอบแทน
        """
        blocks = []
        hits = self.search_guide(keyword)
        if hits:
            rows = []
            for step, item in hits[:4]:
                menu_text = self._item_menu_text(item)
                rows.append(u'<div class="mb-2"><b>%s</b><br/>%s<br/>'
                            u'<span class="text-muted">เอาไว้ %s · อยู่ในขั้นที่ %s (%s)</span>'
                            u'</div>' % (
                                html_escape(item['name']), html_escape(menu_text),
                                html_escape(item['what']), step['order'],
                                html_escape(step['title'])))
            blocks.append(u'<b>เมนูที่เกี่ยวกับ "%s"</b>' % html_escape(keyword))
            blocks += rows

        found = self.find_menus(keyword, limit=4)
        # ถ้าคู่มือตอบไปแล้ว ไม่ต้องยัดรายการซ้ำ เว้นแต่ค้นเจอที่คู่มือไม่มี
        known = u' '.join(blocks)
        extra = [item for item in found if item['path'] not in known]
        if extra:
            rows = []
            for item in extra:
                note = u'' if item['visible'] else \
                    u'<br/><span class="text-muted">สิทธิ์ของคุณยังไม่เห็นเมนูนี้ — ' \
                    u'ให้ IT ตั้ง Invoicing = Billing Administrator</span>'
                rows.append(u'<div class="mb-1">%s%s</div>' % (html_escape(item['path']), note))
            if not blocks:
                blocks.append(u'<b>เมนูที่ใกล้เคียง "%s"</b>' % html_escape(keyword))
            blocks += rows
        return blocks

    # ==================================================================
    # ไฟล์ Excel
    # ==================================================================
    @api.model
    def build_excel(self, years):
        u"""ชีตแรก = เช็คลิสต์ทุกปีที่ถาม ชีตถัดไป = รายการที่ติดของแต่ละปี

        คืน (ชื่อไฟล์, ไบต์, จำนวนแถวรวม) -- (None, None, 0) ถ้าสร้างไม่ได้
        """
        if not xlsxwriter:
            return None, None, 0
        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {'in_memory': True})
        head = book.add_format({'bold': True, 'bg_color': '#DDEBF7', 'border': 1,
                                'font_name': 'Tahoma', 'font_size': 10, 'text_wrap': True,
                                'valign': 'top'})
        text = book.add_format({'font_name': 'Tahoma', 'font_size': 10, 'valign': 'top'})
        wrap = book.add_format({'font_name': 'Tahoma', 'font_size': 10, 'text_wrap': True,
                                'valign': 'top'})
        money = book.add_format({'num_format': '#,##0.00', 'font_name': 'Tahoma',
                                 'font_size': 10})
        title = book.add_format({'bold': True, 'font_name': 'Tahoma', 'font_size': 12})

        summary = book.add_worksheet(u'เช็คลิสต์ปิดงบ')
        headers = [u'ปี', u'สถานะ', u'รายการ', u'ที่พบ', u'เท่าไหร่ถึงจะถูก',
                   u'เมนูที่ต้องไปทำ', u'วิธีแก้']
        widths = [8, 14, 28, 44, 44, 46, 50]
        for index, header in enumerate(headers):
            summary.write(0, index, header, head)
            summary.set_column(index, index, widths[index])
        summary.freeze_panes(1, 0)

        row_index = 1
        total_rows = 0
        detail_sheets = []
        for year in years:
            checks = self.run_checks(year)
            verdict = self.verdict(year, checks=checks)
            for check in checks:
                summary.write(row_index, 0, year, text)
                summary.write(row_index, 1, STATUS_LABEL.get(check['status'], u''), text)
                summary.write(row_index, 2, check['title'], wrap)
                summary.write(row_index, 3, check['found'] or u'-', wrap)
                summary.write(row_index, 4, check['need'] or u'-', wrap)
                summary.write(row_index, 5, check['menu_path'] or u'-', wrap)
                summary.write(row_index, 6, check['fix'] or u'-', wrap)
                row_index += 1
                total_rows += 1
                if check['rows']:
                    detail_sheets.append((year, check))
            summary.write(row_index, 0, year, text)
            summary.write(row_index, 1, u'สรุป', text)
            summary.write(row_index, 2,
                          u'ปิดงบสมบูรณ์' if verdict['complete'] else u'ยังปิดงบไม่สมบูรณ์', wrap)
            summary.write(row_index, 3,
                          u'ติด %s เรื่อง / ควรดู %s เรื่อง'
                          % (len(verdict['blocking']), len(verdict['warnings'])), wrap)
            row_index += 2

        used_names = set()
        for year, check in detail_sheets:
            name = (u'%s-%s' % (year, check['title']))[:28]
            suffix = 1
            while name in used_names:
                suffix += 1
                name = (u'%s-%s(%s)' % (year, check['title'], suffix))[:28]
            used_names.add(name)
            sheet = book.add_worksheet(name)
            sheet.write(0, 0, u'%s ปี %s' % (check['title'], year), title)
            headers = [column[0] for column in check['columns']]
            keys = [column[1] for column in check['columns']]
            for index, header in enumerate(headers):
                sheet.write(2, index, header, head)
                sheet.set_column(index, index, max(14, min(40, len(header) + 10)))
            sheet.freeze_panes(3, 0)
            for offset, record in enumerate(check['rows']):
                for col_index, key in enumerate(keys):
                    value = record.get(key)
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        sheet.write(3 + offset, col_index, str(value[1] or u''), text)
                    elif value in (False, None):
                        sheet.write(3 + offset, col_index, u'', text)
                    elif isinstance(value, (int, float)) and not isinstance(value, bool):
                        sheet.write_number(3 + offset, col_index, value, money)
                    else:
                        sheet.write(3 + offset, col_index, str(value)[:200], text)
                total_rows += 1

        book.close()
        label = u'-'.join(str(y) for y in years) or str(date.today().year)
        return u'ปิดงบ-%s.xlsx' % label, stream.getvalue(), total_rows

    # ==================================================================
    # ลงมือแก้ให้ + ถอยกลับ + ส่งงานที่ AI ทำไม่ได้กลับไปให้พนักงาน
    # ==================================================================
    @api.model
    def detect_fix(self, question):
        u"""อ่านว่าพนักงานสั่งให้ทำอะไร คืน (โหมด, key)

        โหมด: 'fix' = ให้ลงมือแก้ / 'undo' = ให้ถอย / None = ไม่ใช่คำสั่ง
        """
        text = (question or u'').lower()
        if any(w in text for w in UNDO_WORDS):
            return 'undo', 'all' if any(w in text for w in ALL_WORDS) else 'list'
        if not any(v in text for v in FIX_VERBS):
            return None, None
        if any(w in text for w in (u'cut-off', u'cutoff', u'คัทออฟ', u'ค้างรับ', u'ค้างจ่าย')):
            return 'fix', 'cutoff_journal'
        if any(w in text for w in (u'ปีบัญชี', u'fiscal year', u'ปีบัญชี')):
            return 'fix', 'fiscal_year'
        if any(w in text for w in (u'แม่แบบ', u'template', u'ใบปิด')):
            return 'fix', 'closing_template'
        if any(w in text for w in (u'ล็อก', u'ล๊อก', u'lock')):
            return 'fix', 'lock_date'
        if any(w in text for w in (u'ให้หมด', u'ทุกอย่างที่ทำได้', u'เท่าที่ทำได้')):
            return 'fix', 'all'
        return None, None

    @api.model
    def detect_options(self, question):
        u"""อ่านคำสั่งของฝ่ายบัญชีที่ขอเปลี่ยนค่าตั้งต้น

        บัญชีเป็นคนตัดสินใจ ไม่ใช่ AI -- พิมพ์บอกได้เลย เช่น
            "ปิดเข้า 3200-00"  /  "ใช้สมุด MISC"
        คืน dict {'dest_code': ..., 'journal_code': ...} เฉพาะที่ระบุมา
        """
        text = question or u''
        options = {}
        match = re.search(r'(\d{4}-\d{2})', text)
        if match:
            options['dest_code'] = match.group(1)
        match = re.search(r'(?:สมุด|journal)\s*([A-Za-z]{2,6})', text)
        if match:
            options['journal_code'] = match.group(1).upper()
        return options

    @api.model
    def _closing_journal(self, code=None):
        Journal = self.env['account.journal'].sudo()
        for want in ([code] if code else []) + ['JV', 'MISC']:
            j = Journal.search([('company_id', '=', self._company().id),
                                ('type', '=', 'general'), ('code', '=', want)], limit=1)
            if j:
                return j
        return Journal.search([('company_id', '=', self._company().id),
                               ('type', '=', 'general')], limit=1)

    @api.model
    def _profit_account(self, code=None):
        u"""บัญชีปลายทางที่จะปิดกำไรเข้า

        ค่าตั้งต้นคือกำไร(ขาดทุน) แต่ถ้าฝ่ายบัญชีสั่งมาเป็นรหัสอื่น ใช้ตามบัญชีสั่ง
        (ผังบัญชีแต่ละบริษัทรหัสไม่ตรงกัน และเป็นดุลพินิจของบัญชีว่าจะปิดเข้าตัวไหน)
        """
        Account = self.env['account.account'].sudo()
        if code:
            wanted = Account.search([('company_id', '=', self._company().id),
                                     ('code', '=', code)], limit=1)
            if wanted:
                return wanted
        for code in ('3320-00', '3300-00', '3202-00', '3200-00'):
            a = Account.search([('company_id', '=', self._company().id),
                                ('code', '=', code)], limit=1)
            if a:
                return a
        return Account.browse()

    # ------------------------------------------------------------------
    # ลิงก์ไปหน้าที่ต้องไปแก้
    #
    # เอกสารฉบับร่างหลายใบยังไม่มีเลขที่ (ขึ้นเป็น "/") พนักงานจึงค้นจากเลขไม่ได้
    # กรณีแบบนี้ต้องแนบ URL ของหน้านั้นไปให้เลย (หลักการเดียวกับหัวข้อแก้วันที่
    # ใบแจ้งหนี้ ที่ให้วาง URL เพราะฉบับร่างไม่มีเลขที่)
    # ------------------------------------------------------------------
    @api.model
    def _base_url(self):
        return (self.env['ir.config_parameter'].sudo()
                .get_param('web.base.url') or u'').rstrip('/')

    @api.model
    def doc_url(self, record):
        u"""ลิงก์เปิดเอกสารใบนั้นตรง ๆ"""
        base = self._base_url()
        if not base or not record:
            return u''
        return u'%s/web#id=%s&model=%s&view_type=form' % (base, record.id, record._name)

    @api.model
    def action_url(self, xmlid):
        u"""ลิงก์เปิดหน้าจอจาก xmlid ของ action (เช่นหน้าตั้งวันที่ล็อก)"""
        base = self._base_url()
        action = self.env.ref(xmlid, raise_if_not_found=False)
        if not base or not action:
            return u''
        return u'%s/web#action=%s' % (base, action.id)

    @api.model
    def _where_to_fix(self, label, xmlid, menu_find, menu_path, extra=u''):
        u"""บรรทัด "ไปแก้ที่ไหน" พร้อมเมนูจริงและลิงก์"""
        menu = self._item_menu_text({'find': menu_find, 'path': menu_path})
        url = self.action_url(xmlid)
        text = u'<div><span class="text-muted">ไปแก้ที่</span> %s' % html_escape(menu)
        if url:
            text += u'<br/><a href="%s">%s</a>' % (html_escape(url), html_escape(url))
        if extra:
            text += u'<br/><span class="text-muted">%s</span>' % extra
        return text + u'</div>'

    @api.model
    def _lock_allowed(self, lock_date):
        u"""Odoo ยอมให้ล็อกได้ไม่เกินวันสิ้นเดือนก่อนหน้าเท่านั้น

        ถ้าปีที่จะปิดยังไม่จบ จะล็อกวันสิ้นปีไม่ได้ ต้องรอให้ถึงเวลาก่อน
        """
        today = date.today()
        last_day_prev_month = date(today.year, today.month, 1) - timedelta(days=1)
        return lock_date <= last_day_prev_month

    @api.model
    def fix_preview(self, key, year, options=None):
        u"""บอกว่าจะทำอะไรก่อนขอคำยืนยัน คืน (หัวข้อ, [บรรทัด], ข้อความผิดพลาด)"""
        keys = list(FIX_ACTIONS) if key == 'all' else [key]
        options = options or {}
        company = self._company()
        dfrom, dto = self.fiscal_window(year)
        rows, todo = [], 0

        for k in keys:
            if k == 'cutoff_journal':
                current = company.sudo().default_cutoff_journal_id
                journal = self._closing_journal()
                if current:
                    rows.append(u'<div>%s — ตั้งไว้แล้ว (%s) ข้าม</div>'
                                % (FIX_LABEL[k], html_escape(current.name or u'')))
                elif not journal:
                    rows.append(u'<div>%s — <b>ไม่มีสมุดรายวันทั่วไป</b> ต้องสร้างก่อน</div>'
                                % FIX_LABEL[k])
                else:
                    todo += 1
                    rows.append(u'<div><b>%s</b> → %s (%s)</div>'
                                % (FIX_LABEL[k], html_escape(journal.name or u''),
                                   html_escape(journal.code or u'')))
            elif k == 'fiscal_year':
                if 'account.fiscal.year' not in self.env:
                    continue
                found = self.env['account.fiscal.year'].sudo().search(
                    [('company_id', '=', company.id), ('date_from', '<=', dto),
                     ('date_to', '>=', dfrom)], limit=1)
                if found:
                    rows.append(u'<div>%s — มีแล้ว (%s) ข้าม</div>'
                                % (FIX_LABEL[k], html_escape(found.name or u'')))
                else:
                    todo += 1
                    rows.append(u'<div><b>%s %s</b> → %s ถึง %s</div>'
                                % (FIX_LABEL[k], year, _thai_date(dfrom), _thai_date(dto)))
            elif k == 'closing_template':
                if 'account.fiscalyear.closing.template' not in self.env:
                    continue
                T = self.env['account.fiscalyear.closing.template'].sudo()
                usable = [t for t in T.search([])
                          if any(c.mapping_ids for c in t.move_config_ids)]
                dest = self._profit_account(options.get('dest_code'))
                journal = self._closing_journal(options.get('journal_code'))
                if usable:
                    rows.append(u'<div>%s — มีแม่แบบที่ใช้ได้แล้ว (%s) ข้าม</div>'
                                % (FIX_LABEL[k], html_escape(usable[0].name or u'')))
                elif not dest or not journal:
                    rows.append(u'<div>%s — <b>หาบัญชีปลายทางหรือสมุดรายวันไม่เจอ</b></div>'
                                % FIX_LABEL[k])
                else:
                    todo += 1
                    rows.append(u'<div><b>%s ปี %s</b><br/>'
                                u'ปิดบัญชีรหัส 4%% · 5%% · 6%% (แยก 3 บรรทัด) '
                                u'เข้าบัญชี <b>%s %s</b> ผ่านสมุด %s</div>'
                                % (FIX_LABEL[k], year, html_escape(dest.code or u''),
                                   html_escape(dest.name or u''), html_escape(journal.code or u'')))
            elif k == 'lock_date':
                current = company.sudo().fiscalyear_lock_date
                if current and current >= dto:
                    rows.append(u'<div>%s — ล็อกถึง %s อยู่แล้ว ข้าม</div>'
                                % (FIX_LABEL[k], _thai_date(current)))
                elif not self._lock_allowed(dto):
                    # Odoo ห้ามล็อกงวดที่ยังไม่จบ (ต้องไม่เกินวันสิ้นเดือนก่อนหน้า)
                    rows.append(u'<div>%s — <b>ยังล็อกไม่ได้</b> เพราะงวดสิ้นสุด %s '
                                u'ยังมาไม่ถึง ระบบให้ล็อกได้ไม่เกินสิ้นเดือนที่แล้ว</div>%s'
                                % (FIX_LABEL[k], _thai_date(dto),
                                   self._where_to_fix(
                                       FIX_LABEL[k],
                                       'account_lock_date_update.account_update_lock_date_act_window',
                                       u'lock dates',
                                       u'Accounting > Accounting > Actions > Update accounting lock dates',
                                       u'ทำได้ตั้งแต่ %s เป็นต้นไป' % _thai_date(
                                           date(dto.year + 1, 1, 1)))))
                else:
                    todo += 1
                    rows.append(u'<div><b>%s</b> → ล็อกถึง %s (เดิม %s)</div>'
                                % (FIX_LABEL[k], _thai_date(dto), _thai_date(current)))
        if not todo:
            return u'', rows, u'ไม่มีอะไรต้องตั้งเพิ่ม ทุกอย่างในรายการนี้ตั้งไว้ครบแล้ว'
        rows.append(
            u'<div class="mb-2"><span class="text-muted">ค่าพวกนี้ผมเลือกจากข้อมูลที่เห็น '
            u'<b>ถือเป็นค่าตั้งต้น ไม่ใช่คำตัดสิน</b> — ฝ่ายบัญชีเปลี่ยนได้ '
            u'พิมพ์บอกได้เลย เช่น "ปิดเข้า 3200-00" หรือ "ใช้สมุด MISC" '
            u'แล้วผมจะเสนอใหม่ตามนั้น</span></div>')
        return (u'จะลงมือแก้ %s เรื่อง (ปี %s)' % (todo, year)), rows, u''

    @api.model
    def fix_apply(self, key, year, session=None, options=None):
        u"""ลงมือทำจริง ทุกก้าวบันทึกลง npd.ai.it.closing.fix เพื่อให้ถอยได้

        คืน (batch, [ข้อความสิ่งที่ทำ], ข้อความผิดพลาด)
        """
        keys = list(FIX_ACTIONS) if key == 'all' else [key]
        options = options or {}
        Fix = self.env['npd.ai.it.closing.fix']
        company = self._company()
        dfrom, dto = self.fiscal_window(year)
        batch = 'fix-%s-%s' % (year, fields_now())
        done, failed = [], []

        for k in keys:
            try:
                with self.env.cr.savepoint():
                    if k == 'cutoff_journal':
                        if company.sudo().default_cutoff_journal_id:
                            continue
                        journal = self._closing_journal(options.get('journal_code'))
                        if not journal:
                            continue
                        old = False
                        company.sudo().write({'default_cutoff_journal_id': journal.id})
                        Fix.log_write(company, 'default_cutoff_journal_id', old, journal.id,
                                      k, u'%s = %s' % (FIX_LABEL[k], journal.code or journal.name),
                                      batch=batch, session=session, year=year)
                        done.append(u'%s → %s' % (FIX_LABEL[k], journal.code or journal.name))

                    elif k == 'fiscal_year' and 'account.fiscal.year' in self.env:
                        FY = self.env['account.fiscal.year'].sudo()
                        if FY.search_count([('company_id', '=', company.id),
                                            ('date_from', '<=', dto), ('date_to', '>=', dfrom)]):
                            continue
                        rec = FY.create({'name': u'ปี %s' % year, 'date_from': dfrom,
                                         'date_to': dto, 'company_id': company.id})
                        Fix.log_create(rec, k, u'%s %s' % (FIX_LABEL[k], year),
                                       batch=batch, session=session, year=year)
                        done.append(u'%s %s (%s ถึง %s)'
                                    % (FIX_LABEL[k], year, _thai_date(dfrom), _thai_date(dto)))

                    elif k == 'closing_template' and 'account.fiscalyear.closing.template' in self.env:
                        T = self.env['account.fiscalyear.closing.template'].sudo()
                        if any(any(c.mapping_ids for c in t.move_config_ids) for t in T.search([])):
                            continue
                        dest = self._profit_account(options.get('dest_code'))
                        journal = self._closing_journal(options.get('journal_code'))
                        if not dest or not journal:
                            continue
                        vals = {
                            'name': u'ปิดงบ %s' % year,
                            'check_draft_moves': True,
                            'company_id': company.id,
                            'move_config_ids': [(0, 0, {
                                'name': u'ปิดกำไรขาดทุน %s' % year,
                                'code': 'PL_%s' % year, 'sequence': 1,
                                'move_type': 'loss_profit', 'move_date': 'last_ending',
                                'journal_id': journal.id, 'closing_type_default': 'balance',
                                # ต้องแยกบรรทัดต่อรูปแบบ ระบบเทียบแบบ =ilike ทีละบรรทัด
                                # ใส่ '4%,5%,6%' รวมกันจะไม่ตรงบัญชีไหนเลย
                                'mapping_ids': [(0, 0, {'name': u'ปิด %s' % p,
                                                        'src_accounts': p,
                                                        'dest_account': dest.code})
                                                for p in ('4%', '5%', '6%')],
                            })],
                        }
                        if company.chart_template_id:
                            vals['chart_template_ids'] = [(6, 0, [company.chart_template_id.id])]
                        rec = T.create(vals)
                        Fix.log_create(rec, k, u'%s ปี %s (ปิดเข้า %s)'
                                       % (FIX_LABEL[k], year, dest.code),
                                       batch=batch, session=session, year=year)
                        done.append(u'%s ปี %s → ปิด 4%%/5%%/6%% เข้าบัญชี %s'
                                    % (FIX_LABEL[k], year, dest.code))

                    elif k == 'lock_date':
                        current = company.sudo().fiscalyear_lock_date
                        if current and current >= dto:
                            continue
                        if not self._lock_allowed(dto):
                            failed.append(
                                u'%s — ยังล็อกไม่ได้ งวดสิ้นสุด %s ยังมาไม่ถึง '
                                u'(ระบบให้ล็อกได้ไม่เกินสิ้นเดือนที่แล้ว) '
                                u'ทำได้ตั้งแต่ %s · เมนู %s'
                                % (FIX_LABEL[k], _thai_date(dto),
                                   _thai_date(date(dto.year + 1, 1, 1)),
                                   self._item_menu_text({
                                       'find': u'lock dates',
                                       'path': u'Accounting > Accounting > Actions > '
                                               u'Update accounting lock dates'})))
                            continue
                        company.sudo().write({'fiscalyear_lock_date': dto})
                        Fix.log_write(company, 'fiscalyear_lock_date', current and str(current),
                                      str(dto), k, u'%s ถึง %s' % (FIX_LABEL[k], _thai_date(dto)),
                                      batch=batch, session=session, year=year)
                        done.append(u'%s ถึง %s' % (FIX_LABEL[k], _thai_date(dto)))
            except Exception as exc:  # noqa: BLE001 - งานหนึ่งพังต้องไม่ล้มทั้งชุด
                _logger.warning(u'ช่วยปิดงบ: ทำ %s ไม่สำเร็จ (%s)', k, exc)
                failed.append(u'%s — %s' % (FIX_LABEL.get(k, k), str(exc)[:120]))
        if not done and not failed:
            return batch, [], [], u'ไม่มีอะไรต้องทำเพิ่ม'
        return batch, done, failed, u''

    # ------------------------------------------------------------------
    @api.model
    def undo_list(self, limit=12):
        u"""รายการที่ AI เคยแก้ให้และยังถอยได้"""
        return self.env['npd.ai.it.closing.fix'].sudo().search(
            [('state', '=', 'done'), ('company_id', 'in', (self._company().id, False))],
            limit=limit)

    @api.model
    def undo_blocks(self):
        u"""แสดงรายการที่ถอยได้ พร้อมวิธีสั่งถอยทีละรายการหรือถอยทั้งหมด"""
        fixes = self.undo_list()
        if not fixes:
            return [u'<b>ยังไม่มีรายการที่ผมแก้ให้ในปีนี้</b> จึงไม่มีอะไรให้ถอย']
        rows = [u'<tr><th style="text-align:left">ข้อ</th>'
                u'<th style="text-align:left">สิ่งที่แก้</th>'
                u'<th style="text-align:left">เมื่อ</th></tr>']
        for index, fix in enumerate(fixes, start=1):
            rows.append(u'<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
                        % (index, html_escape(fix.title or u''),
                           fields.Datetime.context_timestamp(fix, fix.date).strftime('%d/%m/%Y %H:%M')))
        return [u'<b>รายการที่ผมแก้ให้ และยังถอยกลับได้</b>',
                u'<table class="table table-sm" style="width:100%%">%s</table>' % u''.join(rows),
                _hint_fix(u'พิมพ์ "ถอยข้อ 2" เพื่อถอยเฉพาะรายการนั้น '
                          u'หรือ "ถอยทั้งหมด" เพื่อถอยทุกรายการข้างบน')]

    @api.model
    def undo_apply(self, index=None):
        u"""ถอยกลับ -- ระบุข้อ = ถอยรายการเดียว / ไม่ระบุ = ถอยทั้งหมด

        คืน (จำนวนที่ถอยสำเร็จ, [ปัญหา])
        """
        fixes = self.undo_list()
        if not fixes:
            return 0, [u'ไม่มีรายการให้ถอย']
        if index:
            if index < 1 or index > len(fixes):
                return 0, [u'ไม่มีข้อ %s ในรายการ' % index]
            fixes = fixes[index - 1]
        return fixes.action_undo()

    # ------------------------------------------------------------------
    @api.model
    def worklist_blocks(self, year, limit=10):
        u"""งานที่ AI ทำให้ไม่ได้ ต้องให้พนักงานแก้เอง พร้อมเลขที่เอกสาร

        ผู้ใช้สั่งว่า ให้ดึงข้อมูลที่พนักงานต้องแก้ออกมาก่อน พอแก้เสร็จค่อยให้
        AI ตรวจต่อจากข้อมูลที่แก้แล้ว -- ฟังก์ชันนี้คือส่วน "ดึงข้อมูลออกมา"
        """
        company = self._company()
        dfrom, dto = self.fiscal_window(year)
        blocks, any_work = [], False

        Move = self.env['account.move'].sudo()
        drafts = Move.search([('company_id', '=', company.id), ('state', '=', 'draft'),
                              ('date', '>=', dfrom), ('date', '<=', dto)],
                             order='date, name')
        if drafts:
            any_work = True
            rows = [u'<tr><th style="text-align:left">เลขที่ / อ้างอิง</th>'
                    u'<th style="text-align:left">วันที่</th>'
                    u'<th style="text-align:left">สมุด</th>'
                    u'<th style="text-align:right">ยอด</th>'
                    u'<th style="text-align:left">เปิดเอกสาร</th></tr>']
            for mv in drafts[:limit]:
                # ใบร่างหลายใบยังไม่มีเลขที่ ต้องให้ลิงก์ไปเลย ไม่งั้นค้นไม่เจอ
                has_number = mv.name and mv.name != '/'
                label = mv.name if has_number else (mv.ref or u'(ยังไม่มีเลขที่)')
                url = self.doc_url(mv)
                link = (u'<a href="%s">เปิด</a>' % html_escape(url)) if url else u'—'
                if not has_number and url:
                    link = u'<a href="%s">%s</a>' % (html_escape(url), html_escape(url))
                rows.append(u'<tr><td>%s</td><td>%s</td><td>%s</td>'
                            u'<td style="text-align:right">%s</td><td>%s</td></tr>'
                            % (html_escape(label), _thai_date(mv.date),
                               html_escape(mv.journal_id.code or u''),
                               _money(mv.amount_total), link))
            more = (u'<div><span class="text-muted">แสดง %s จาก %s ใบ — '
                    u'ขอเป็นไฟล์ Excel เพื่อดูครบ</span></div>'
                    % (min(limit, len(drafts)), len(drafts))) if len(drafts) > limit else u''
            blocks.append(u'<b>1. ใบค้างร่าง %s ใบ — ต้องกด Post หรือ Cancel เอง</b>'
                          u'<div><span class="text-muted">AI ตัดสินใจแทนไม่ได้ '
                          u'ต้องดูทีละใบว่ารายการถูกไหม · ใบที่ยังไม่มีเลขที่ '
                          u'ให้กดจากลิงก์ เพราะค้นด้วยเลขไม่ได้</span></div>'
                          u'<table class="table table-sm" style="width:100%%">%s</table>%s%s'
                          % (len(drafts), u''.join(rows), more,
                             self._where_to_fix(
                                 u'ใบค้างร่าง', 'account.action_move_journal_line',
                                 u'Journal Entries',
                                 u'Accounting > Accounting > Miscellaneous > Journal Entries',
                                 u'กรอง Draft + ปี %s' % year)))

        self.env.cr.execute(
            """SELECT m.id, m.name, m.date, j.code,
                      ROUND((t.d - t.c)::numeric, 2), COUNT(*) OVER ()
                 FROM account_move m
                 JOIN account_journal j ON j.id = m.journal_id
                 JOIN (SELECT move_id, SUM(debit) d, SUM(credit) c
                         FROM account_move_line GROUP BY move_id) t ON t.move_id = m.id
                WHERE m.company_id = %s AND m.state = 'posted'
                  AND m.date >= %s AND m.date <= %s AND ABS(t.d - t.c) > 0.004
                ORDER BY ABS(t.d - t.c) DESC LIMIT %s""",
            (company.id, dfrom, dto, limit))
        bad = self.env.cr.fetchall()
        if bad:
            any_work = True
            total = bad[0][5]
            rows = [u'<tr><th style="text-align:left">เลขที่</th>'
                    u'<th style="text-align:left">วันที่</th>'
                    u'<th style="text-align:left">สมุด</th>'
                    u'<th style="text-align:right">ผลต่าง</th>'
                    u'<th style="text-align:left">เปิดเอกสาร</th></tr>']
            Move = self.env['account.move'].sudo()
            for move_id, name, date_, code, diff, _n in bad:
                url = self.doc_url(Move.browse(move_id))
                link = (u'<a href="%s">เปิด</a>' % html_escape(url)) if url else u'—'
                rows.append(u'<tr><td>%s</td><td>%s</td><td>%s</td>'
                            u'<td style="text-align:right">%s</td><td>%s</td></tr>'
                            % (html_escape(name or u'(ยังไม่มีเลขที่)'), _thai_date(date_),
                               html_escape(code or u''), _money(diff), link))
            blocks.append(u'<b>2. ใบที่เดบิตไม่เท่าเครดิต %s ใบ — ต้องให้ IT กับบัญชีดูร่วมกัน</b>'
                          u'<div><span class="text-muted">เป็นข้อมูลผิดปกติ ไม่ใช่ขั้นตอนปิดงบ '
                          u'AI จะไม่เติมบรรทัดให้ลงตัวเอง เพราะต้องรู้ต้นเหตุก่อน</span></div>'
                          u'<table class="table table-sm" style="width:100%%">%s</table>'
                          % (total, u''.join(rows)))

        if 'account.asset' in self.env:
            n_draft = self.env['account.asset'].sudo().search_count(
                [('company_id', '=', company.id), ('state', '=', 'draft')])
            if n_draft:
                any_work = True
                blocks.append(u'<b>3. สินทรัพย์สถานะร่าง %s รายการ — ต้องยืนยันเอง</b>'
                              u'<div><span class="text-muted">กระทบค่าเสื่อมทั้งปี '
                              u'ต้องตกลงก่อนว่าจะคุมค่าเสื่อมใน Odoo หรือ Excel</span></div>%s'
                              % (n_draft, self._where_to_fix(
                                  u'สินทรัพย์', 'account_asset_management.account_asset_action',
                                  u'Assets', u'Accounting > Assets')))

        if not any_work:
            return [u'<b>🟢 ไม่มีงานที่ต้องให้พนักงานแก้เองแล้ว</b> '
                    u'เหลือแต่ขั้นตอนที่ผมทำให้ได้']
        blocks.insert(0, u'<b>งานที่ผมทำให้ไม่ได้ ต้องให้คนทำเอง — ปี %s</b>' % year)
        blocks.append(_hint_fix(
            u'แก้เสร็จแล้วพิมพ์ "ตรวจต่อ" ผมจะตรวจใหม่จากข้อมูลล่าสุดให้'))
        blocks.append(_hint_fix(
            u'รายการข้างบนเป็นสิ่งที่ "ระบบตรวจเจอ" ฝ่ายบัญชีอาจเห็นว่าบางข้อ'
            u'ไม่ต้องแก้ หรือต้องแก้คนละแบบ — บอกผมได้ ผมปรับตามที่บัญชีตัดสิน'))
        return blocks

    # ==================================================================
    # ตอบคำถามอิสระด้วย AI (ยึดคู่มือ + ผลตรวจจริง + เมนูจริง)
    # ==================================================================
    @api.model
    def _kb_text(self):
        parts = []
        for step in CLOSING_STEPS:
            lines = [u'ขั้นที่ %s %s — %s (เหตุผล: %s)'
                     % (step['order'], step['title'], step['goal'], step['why'])]
            for item in step['items']:
                lines.append(u'  - %s | เมนู: %s | ทำอะไร: %s | ผ่านเมื่อ: %s'
                             % (item['name'], item['path'], item['what'], item['pass']))
            parts.append(u'\n'.join(lines))
        parts.append(u'อาการที่เจอบ่อย:\n' + u'\n'.join(
            u'  - %s => สาเหตุ: %s => แก้: %s' % row for row in PITFALLS))
        return u'\n\n'.join(parts)

    @api.model
    def _checks_text(self, year, checks):
        lines = [u'ผลตรวจจริงของปี %s (ค.ศ.) / พ.ศ. %s:' % (year, year + 543)]
        for check in checks:
            lines.append(u'  - [%s] %s | พบ: %s | ต้องเป็น: %s | เมนู: %s'
                         % (STATUS_LABEL.get(check['status'], check['status']),
                            check['title'], check['found'] or u'-',
                            check['need'] or u'-', check['menu_path'] or u'-'))
        return u'\n'.join(lines)

    @api.model
    def ai_answer(self, question, year, checks, history=None, extra=None):
        u"""ให้ AI ตอบคำถามอิสระ โดยห้ามออกนอกข้อมูลที่ให้ไป

        extra = ข้อความบริบทเพิ่ม (เช่น สรุปสถานะของปีอื่นตอนถามหลายปี)
        คืน (list ของบรรทัดคำตอบ, ข้อความผิดพลาด)
        """
        Gemini = self.env['npd.ai.it.gemini']
        if not Gemini.is_available():
            return [], u'ยังไม่ได้ตั้งค่า AI Key'

        # ดึงเมนูจริงที่เกี่ยวกับคำในคำถาม ให้ AI อ้างได้โดยไม่ต้องเดา
        menu_hits = []
        for word in re.findall(r'[A-Za-z][A-Za-z ]{2,}', question or u''):
            for item in self.find_menus(word.strip(), limit=2):
                if item['path'] not in menu_hits:
                    menu_hits.append(item['path'])
        for step in CLOSING_STEPS:
            for item in step['items']:
                if item['name'] in (question or u''):
                    path = self._item_menu_text(item)
                    if path not in menu_hits:
                        menu_hits.append(path)

        history_text = u''
        if history:
            history_text = u'\nคำถามก่อนหน้า (ใช้ต่อยอดได้):\n%s\n' % json.dumps(
                history, ensure_ascii=False)[:800]

        prompt = (
            u'คุณเป็นผู้ช่วยฝ่ายบัญชีของบริษัทให้เช่าอุปกรณ์ก่อสร้าง ที่ใช้ Odoo 14\n'
            u'ตอบคำถามเรื่อง "การปิดงบสิ้นปี" ให้นักบัญชีเข้าใจ\n\n'
            u'=== คู่มือปิดงบของระบบนี้ (ข้อมูลจริง ห้ามขัดแย้ง) ===\n%s\n\n'
            u'=== ผลตรวจจากฐานข้อมูลจริง ===\n%s\n%s\n'
            u'=== เมนูจริงที่ค้นเจอในระบบนี้ ===\n%s\n'
            u'%s\n'
            u'=== คำถาม ===\n"""%s"""\n\n'
            u'กติกาการตอบ\n'
            u'- ตอบสั้น สรุป แบบที่นักบัญชีอ่านแล้วทำงานต่อได้ทันที ห้ามเยิ่นเย้อ\n'
            u'- อ้างตัวเลขได้เฉพาะตัวเลขที่อยู่ในผลตรวจข้างบนเท่านั้น ห้ามคิดเลขใหม่เอง\n'
            u'- อ้างชื่อเมนูได้เฉพาะที่อยู่ในคู่มือหรือรายการเมนูจริงข้างบนเท่านั้น '
            u'ห้ามแต่งชื่อเมนูขึ้นมาเอง\n'
            u'- ถ้าคำถามอยู่นอกเรื่องปิดงบ ให้ตอบ {"error": "เหตุผลสั้น ๆ"}\n'
            u'- ถ้าข้อมูลที่ให้มาไม่พอจะตอบ ให้บอกตรง ๆ ว่าต้องไปดูเมนูไหนเพิ่ม\n\n'
            u'ตอบเป็น JSON เท่านั้น\n'
            u'{\n'
            u'  "answer": "คำตอบหลัก 1-3 ประโยค",\n'
            u'  "bullets": ["ข้อย่อยสั้น ๆ ไม่เกิน 4 ข้อ"],\n'
            u'  "menus": ["เส้นทางเมนูที่ต้องไป ถ้ามี"]\n'
            u'}'
            % (self._kb_text(), self._checks_text(year, checks), extra or u'',
               u'\n'.join(u'  - %s' % path for path in menu_hits[:12]) or u'  (ไม่มี)',
               history_text, (question or u'')[:600])
        )
        data = Gemini.extract_json(prompt, max_output_tokens=2048)
        if not data:
            return [], u'เรียก AI ไม่สำเร็จ'
        if data.get('error'):
            return [], str(data['error'])[:300]

        blocks = []
        answer = str(data.get('answer') or u'').strip()
        if answer:
            blocks.append(html_escape(answer))
        bullets = [str(b).strip() for b in (data.get('bullets') or []) if str(b).strip()]
        if bullets:
            blocks.append(u'<ul class="mb-0 pl-4">%s</ul>' % u''.join(
                u'<li>%s</li>' % html_escape(b) for b in bullets[:4]))
        menus = [str(m).strip() for m in (data.get('menus') or []) if str(m).strip()]
        if menus:
            blocks.append(u'<span class="text-muted">เมนู</span><br/>%s' % u'<br/>'.join(
                html_escape(m) for m in menus[:4]))
        if not blocks:
            return [], u'AI ตอบกลับมาว่าง'
        return blocks, u''

    # ==================================================================
    # ทางเข้าเดียวที่ session เรียกใช้
    # ==================================================================
    @api.model
    def wants_excel(self, question):
        text = (question or u'').lower()
        return any(word in text for word in EXCEL_WORDS)

    @api.model
    def strip_excel_words(self, question):
        u"""ตัดคำที่แปลว่า "ขอเป็นไฟล์" ออก เหลือแต่เนื้อคำถามจริง"""
        text = question or u''
        for word in EXCEL_WORDS:
            text = text.replace(word, u' ').replace(word.upper(), u' ')
        for word in (u'ขอ', u'เป็น', u'ให้', u'หน่อย', u'ครับ', u'ค่ะ', u'ด้วย', u'ที'):
            text = text.replace(word, u' ')
        return u' '.join(text.split())

    @api.model
    def _has(self, question, words):
        text = (question or u'').lower()
        return any(word in text for word in words)

    @api.model
    def answer(self, question, history=None, years=None):
        u"""คืน (blocks, meta, error)

        meta = {'years': [...], 'kind': 'checks|steps|menu|ai'} เก็บไว้ให้ session
        ใช้ต่อ (เช่นตอนขอไฟล์ Excel ของคำถามเดิม)
        years = บังคับปีเอง (ใช้ตอนพนักงานพิมพ์แค่ "ขอเป็นไฟล์ Excel"
        ต่อจากคำถามก่อนหน้า จะได้ไฟล์ของปีเดิม ไม่ใช่ปีตั้งต้น)
        """
        question = (question or u'').strip()
        parsed = self.parse_years(question)
        meta = {'years': years or parsed or [self.default_year()], 'kind': 'ai'}

        # พิมพ์มาแค่ "ขอเป็นไฟล์ Excel" เฉย ๆ -> แสดงเช็คลิสต์ของปีเดิมซ้ำ
        # ไม่ต้องเสียรอบเรียก AI เพราะไม่ได้ถามอะไรใหม่
        if self.wants_excel(question) and len(self.strip_excel_words(question)) < 8:
            meta['kind'] = 'checks'
            if len(meta['years']) > 1:
                blocks, _details = self.years_blocks(meta['years'])
                return blocks, meta, u''
            return self.checks_blocks(meta['years'][0]), meta, u''

        # 1) ขอแผนที่ขั้นตอน
        step_match = re.search(u'ขั้น(?:ที่)?\\s*([1-4])', question)
        if step_match:
            meta['kind'] = 'steps'
            blocks = self.step_detail_blocks(int(step_match.group(1)))
            return blocks + [self.verdict_line(meta['years'][0])], meta, u''
        if self._has(question, STEP_WORDS) and not self._has(question, CHECK_WORDS):
            meta['kind'] = 'steps'
            return (self.steps_blocks() + [self.verdict_line(meta['years'][0])],
                    meta, u'')

        # 2) ขอผลตรวจ (หลายปี / ปีเดียว)
        wants_check = self._has(question, CHECK_WORDS) or bool(parsed) or bool(years)
        if wants_check:
            meta['kind'] = 'checks'
            if len(meta['years']) > 1:
                blocks, details = self.years_blocks(meta['years'])
                # ถามเป็นคำถามจริง ๆ (ไม่ใช่แค่ "ขอดูสถานะ") -> ให้ AI ตอบต่อท้ายตาราง
                if not self._has(question, CHECK_WORDS) and details:
                    summary = u'สถานะปีอื่นที่ถามมาด้วย:\n' + u'\n'.join(
                        u'  - ปี %s: %s%s' % (
                            item['year'],
                            u'ปิดงบสมบูรณ์แล้ว' if item['complete'] else u'ยังไม่สมบูรณ์',
                            u'' if item['complete'] else u' (ติด %s)' % u', '.join(
                                c['title'] for c in item['blocking'][:4]))
                        for item in details[:-1])
                    extra, _error = self.ai_answer(
                        question, details[-1]['year'], details[-1]['checks'],
                        history=history, extra=summary)
                    blocks += extra
                return blocks, meta, u''
            year = meta['years'][0]
            checks = self.run_checks(year)
            blocks = self.checks_blocks(year, checks=checks)
            # ถามอย่างอื่นมาพร้อมกัน -> ให้ AI เสริมคำอธิบายต่อท้าย
            if not self._has(question, CHECK_WORDS):
                extra, _error = self.ai_answer(question, year, checks, history=history)
                blocks += extra
            return blocks, meta, u''

        # 3) ถามหาเมนู
        if self._has(question, MENU_WORDS):
            keyword = question
            for word in MENU_WORDS + (u'อยู่', u'ที่', u'ไหน', u'ขอ', u'หน่อย', u'ครับ', u'ค่ะ'):
                keyword = keyword.replace(word, u' ')
            keyword = u' '.join(keyword.split())
            if keyword:
                blocks = self.menu_blocks(keyword)
                if blocks:
                    meta['kind'] = 'menu'
                    return (blocks + [self.verdict_line(meta['years'][0])],
                            meta, u'')
                # หาไม่เจอ -> ตกไปให้ AI ตอบ ดีกว่าตอบว่า "ไม่พบ" แล้วจบ

        # 4) คำถามอิสระ -> AI (มีผลตรวจของปีล่าสุดเป็นบริบทเสมอ)
        year = meta['years'][0]
        checks = self.run_checks(year)
        blocks, error = self.ai_answer(question, year, checks, history=history)
        if not error:
            # ถามเรื่องอะไรก็ตาม ต้องปิดท้ายด้วยข้อสรุปว่าปีนั้นปิดงบสมบูรณ์หรือยัง
            blocks = blocks + [self.verdict_line(year, checks=checks)]
            return blocks, meta, u''
        if error:
            # ไม่มี AI หรือ AI ล่ม -> ยังตอบด้วยคู่มือ + ผลตรวจได้
            fallback = self.steps_blocks()
            fallback.append(u'<span class="text-muted">ตอบคำถามนี้ตรง ๆ ไม่ได้ (%s) '
                            u'จึงสรุปขั้นตอนกับผลตรวจปี %s ให้แทน</span>'
                            % (html_escape(error), year))
            fallback += self.checks_blocks(year, checks=checks)
            meta['kind'] = 'fallback'
            return fallback, meta, u''
        return blocks, meta, u''
