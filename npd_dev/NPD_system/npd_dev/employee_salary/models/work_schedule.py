from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HrWorkSchedule(models.Model):
    _name = 'hr.work.schedule'
    _description = 'Work Schedule (Check-in & Shift)'

    _sql_constraints = [
        ('employee_id_uniq', 'unique(employee_id)', 'ไม่สามารถเพิ่มข้อมูลพนักงานซ้ำได้!')
    ]

    employee_id = fields.Many2one('employee.salary', string='ชื่อพนักงาน', required=True)
    employee_code = fields.Char(string='รหัสพนักงาน', readonly=True, related='employee_id.employee_code', required=True)
    position_id = fields.Many2one('hr.position.custom', string='ตำแหน่ง', readonly=True, related='employee_id.position_id')
    department_id = fields.Many2one('hr.department.custom', string='แผนก', readonly=True, related='employee_id.department_id')

    category = fields.Selection([
        ('checkin', 'เช็คอิน'),
        ('no_checkin', 'ไม่ต้องเช็คอิน')
    ], string="หมวดหมู่", default='no_checkin', required=True)

    # วันทำงาน
    work_mon = fields.Boolean("วันจันทร์")
    work_tue = fields.Boolean("วันอังคาร")
    work_wed = fields.Boolean("วันพุธ")
    work_thu = fields.Boolean("วันพฤหัสบดี")
    work_fri = fields.Boolean("วันศุกร์")
    work_sat = fields.Boolean("วันเสาร์")

    # เวลาเริ่ม–เลิกงาน แยกแต่ละวัน (ค่าเริ่มต้น 8.00 – 17.00)
    mon_shift_start = fields.Float("จันทร์ เริ่ม", default=8.0)
    mon_shift_end   = fields.Float("จันทร์ เลิก", default=17.0)

    tue_shift_start = fields.Float("อังคาร เริ่ม", default=8.0)
    tue_shift_end   = fields.Float("อังคาร เลิก", default=17.0)

    wed_shift_start = fields.Float("พุธ เริ่ม", default=8.0)
    wed_shift_end   = fields.Float("พุธ เลิก", default=17.0)

    thu_shift_start = fields.Float("พฤหัส เริ่ม", default=8.0)
    thu_shift_end   = fields.Float("พฤหัส เลิก", default=17.0)

    fri_shift_start = fields.Float("ศุกร์ เริ่ม", default=8.0)
    fri_shift_end   = fields.Float("ศุกร์ เลิก", default=17.0)

    sat_shift_start = fields.Float("เสาร์ เริ่ม", default=8.0)
    sat_shift_end   = fields.Float("เสาร์ เลิก", default=17.0)

    @api.model
    def default_get(self, fields_list):
        """Set default checkboxes for work days"""
        res = super(HrWorkSchedule, self).default_get(fields_list)
        res.update({
            'work_mon': True,
            'work_tue': True,
            'work_wed': True,
            'work_thu': True,
            'work_fri': True,
            'work_sat': True,
        })
        return res

    @api.onchange('category')
    def _onchange_category(self):
        if self.category == 'no_checkin':
            # ปิดวันทำงานและ reset เวลา
            for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat']:
                setattr(self, f'work_{day}', False)
                setattr(self, f'{day}_shift_start', 0.0)
                setattr(self, f'{day}_shift_end', 0.0)
        else:
            # reset ค่า default (8–17)
            for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat']:
                setattr(self, f'work_{day}', True)
                setattr(self, f'{day}_shift_start', 8.0)
                setattr(self, f'{day}_shift_end', 17.0)

    # ✅ ถ้าวันไหนติ๊กออก → เวลาเป็น 0.0, ถ้าติ๊กกลับ → reset เป็น 8.0–17.0
    @api.onchange('work_mon')
    def _onchange_work_mon(self):
        if self.work_mon:
            self.mon_shift_start = 8.0
            self.mon_shift_end = 17.0
        else:
            self.mon_shift_start = 0.0
            self.mon_shift_end = 0.0

    @api.onchange('work_tue')
    def _onchange_work_tue(self):
        if self.work_tue:
            self.tue_shift_start = 8.0
            self.tue_shift_end = 17.0
        else:
            self.tue_shift_start = 0.0
            self.tue_shift_end = 0.0

    @api.onchange('work_wed')
    def _onchange_work_wed(self):
        if self.work_wed:
            self.wed_shift_start = 8.0
            self.wed_shift_end = 17.0
        else:
            self.wed_shift_start = 0.0
            self.wed_shift_end = 0.0

    @api.onchange('work_thu')
    def _onchange_work_thu(self):
        if self.work_thu:
            self.thu_shift_start = 8.0
            self.thu_shift_end = 17.0
        else:
            self.thu_shift_start = 0.0
            self.thu_shift_end = 0.0

    @api.onchange('work_fri')
    def _onchange_work_fri(self):
        if self.work_fri:
            self.fri_shift_start = 8.0
            self.fri_shift_end = 17.0
        else:
            self.fri_shift_start = 0.0
            self.fri_shift_end = 0.0

    @api.onchange('work_sat')
    def _onchange_work_sat(self):
        if self.work_sat:
            self.sat_shift_start = 8.0
            self.sat_shift_end = 17.0
        else:
            self.sat_shift_start = 0.0
            self.sat_shift_end = 0.0


class EmployeeSalaryWorkSchedule(models.Model):
    """แสดงบนเมนู "ข้อมูลพนักงาน" ว่าคนไหนลงตารางกะแล้วหรือยัง

    สำคัญกับการตรวจสอบ เพราะพนักงานที่ยังไม่ลงกะจะถูก **ข้าม** ทั้งการ
    ออกใบเตือนอัตโนมัติ และการคิดสาย/ขาดงานในเงินเดือน โดยไม่มีอะไรฟ้อง
    (hr.work.schedule มี unique(employee_id) อยู่แล้ว = 1 คน 1 กะ)
    """
    _inherit = 'employee.salary'

    work_schedule_id = fields.Many2one(
        'hr.work.schedule', string='ตารางกะ',
        compute='_compute_work_schedule_state')
    work_schedule_state = fields.Selection(
        [('checkin', 'ลงกะแล้ว'),
         ('no_checkin', 'ลงกะแล้ว (ไม่ต้องเช็คอิน)'),
         ('unset', 'ยังไม่ลงกะ')],
        string='สถานะตารางกะ',
        compute='_compute_work_schedule_state',
        search='_search_work_schedule_state',
        help='ยังไม่ลงกะ = ระบบไม่รู้ว่าวันไหนคือวันทำงานของคนนี้\n'
             'จะถูกข้ามทั้งการออกใบเตือนและการคิดสาย/ขาดงานในเงินเดือน')

    def _compute_work_schedule_state(self):
        found = {}
        if self.ids:
            schedules = self.env['hr.work.schedule'].sudo().search(
                [('employee_id', 'in', self.ids)])
            found = {s.employee_id.id: s for s in schedules}
        for rec in self:
            sched = found.get(rec.id)
            rec.work_schedule_id = sched.id if sched else False
            if not sched:
                rec.work_schedule_state = 'unset'
            else:
                rec.work_schedule_state = (
                    'no_checkin' if sched.category == 'no_checkin' else 'checkin')

    def _search_work_schedule_state(self, operator, value):
        """ให้กรอง/ค้นหาได้ ทั้งที่เป็นฟิลด์คำนวณข้ามโมเดล"""
        with_schedule = self.env['hr.work.schedule'].sudo().search(
            []).mapped('employee_id').ids
        values = value if isinstance(value, (list, tuple)) else [value]
        wants_unset = 'unset' in values
        if operator in ('=', 'in'):
            want_set = not wants_unset
        elif operator in ('!=', 'not in'):
            want_set = wants_unset
        else:
            raise UserError(_('ตัวกรองสถานะตารางกะรองรับเฉพาะ = และ != เท่านั้น'))
        return [('id', 'in' if want_set else 'not in', with_schedule)]
