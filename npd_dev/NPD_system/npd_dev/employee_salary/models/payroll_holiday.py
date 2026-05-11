from odoo import models, fields, api

class PayrollHoliday(models.Model):
    """
    Model for creating annual holiday templates.
    """
    _name = 'payroll.holiday'
    _description = 'เทมเพลตวันหยุดประจำปี'
    _order = 'year desc'

    name = fields.Char(
        string='ชื่อเทมเพลต',
        compute='_compute_name',
        store=True,
        readonly=True
        # REMOVED: required=True to fix the creation issue
    )
    year = fields.Integer(
        string='ปี',
        required=True,
        default=lambda self: fields.Date.today().year
    )
    line_ids = fields.One2many(
        'payroll.holiday.line',
        'holiday_id',
        string='รายการวันหยุด'
    )

    _sql_constraints = [
        ('year_uniq', 'unique (year)', 'คุณสามารถสร้างเทมเพลตวันหยุดได้เพียงหนึ่งรายการต่อปี!')
    ]

    @api.depends('year')
    def _compute_name(self):
        """
        Automatically generate the template name based on the year.
        """
        for rec in self:
            if rec.year:
                rec.name = f'วันหยุดประจำปี {rec.year}'
            else:
                rec.name = False

class PayrollHolidayLine(models.Model):
    """
    Model for individual holiday lines within a template.
    """
    _name = 'payroll.holiday.line'
    _description = 'รายการวันหยุด'
    _order = 'date'

    holiday_id = fields.Many2one(
        'payroll.holiday',
        string='เทมเพลตวันหยุด',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(string='ชื่อวันหยุด', required=True)
    date = fields.Date(string='วันที่', required=True)
