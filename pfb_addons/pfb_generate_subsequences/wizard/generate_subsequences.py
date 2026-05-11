from odoo import _, api, fields, models
import pytz
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime
from dateutil.rrule import rrule, DAILY,MONTHLY

class IrSequence(models.Model):
    _inherit = "ir.sequence"

    def generate_sub_sequences(self):
        return {
            'name': _('Generate Sub Sequence'),
            'res_model': 'generate.sub.sequences',
            'view_mode': 'form',
            'context': {
                'active_model': 'ir.sequence',
                'active_ids': self.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
    
    def delete_sub_sequences(self):
        for sub in self.date_range_ids:
            if sub.number_next_actual <= 1:
                sub.sudo().unlink()
class GenerateSubSequences(models.TransientModel):
    _name = "generate.sub.sequences"

    prefix = fields.Char('prefix',default="",required=True)
    year = fields.Integer('Year',required=True,default=2022)
    generate_date_month = fields.Selection([
        ('date', 'Date'),
        ('month','Month'),
    ], 
    string='Generate',
    default='date',
    required=True)

    def action_generate(self):
        start_date = date(self.year, 1, 1)
        end_date = date(self.year, 12, 31)
        
        if self.generate_date_month == 'date':
            self.gent_date(start_date,end_date)
        else:
            self.gent_month(start_date,end_date)
        return True
    
    @api.onchange('generate_date_month')
    def _onchange_generate_date_month(self):
        if self.generate_date_month == 'date':
            self.prefix = '%(month)s%(day)s'
        else:
            self.prefix = '%(month)s'
    
    def _get_prefix_suffix(self, date=None, date_range=None):
        def _interpolate(s, d):
            return (s % d) if s else ''

        def _interpolation_dict():
            now = range_date = effective_date = datetime.now(pytz.timezone(self._context.get('tz') or 'UTC'))
            if date or self._context.get('ir_sequence_date'):
                effective_date = fields.Datetime.from_string(date or self._context.get('ir_sequence_date'))
            sequences = {
                'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j', 'woy': '%W',
                'weekday': '%w', 'h24': '%H', 'h12': '%I', 'min': '%M', 'sec': '%S'
            }
            res = {}
            for key, format in sequences.items():
                res[key] = effective_date.strftime(format)
                res['range_' + key] = range_date.strftime(format)
                res['current_' + key] = now.strftime(format)

            return res

        self.ensure_one()
        d = _interpolation_dict()
        try:
            interpolated_prefix = _interpolate(self.prefix, d)
       
        except ValueError:
            raise UserError(_('Invalid prefix or suffix for sequence \'%s\'') % self.name)
        return interpolated_prefix

    def gent_date(self,start_date,end_date):
        sequence = self.env['ir.sequence'].browse(self._context.get('active_ids', []))
        date_range = self.env['ir.sequence.date_range']
        for d in rrule(DAILY, dtstart=start_date, until=end_date):
            date_range.create({
                'sequence_id':sequence.id,
                'date_from': d,
                'date_to': d,
                'prefix': self._get_prefix_suffix(date=d)
            })
        return True
    
    def gent_month(self,start_date,end_date):
        sequence = self.env['ir.sequence'].browse(self._context.get('active_ids', []))
        date_range = self.env['ir.sequence.date_range']
        for d in rrule(MONTHLY, dtstart=start_date, until=end_date, bymonthday=-1):
            date_from = d.strftime("01-%m-%Y")
            date_obj = datetime.strptime(date_from,"%d-%m-%Y")
            date_range.create({
                'sequence_id':sequence.id,
                'date_from': date_obj,
                'date_to': d,
                'prefix': self._get_prefix_suffix(date=d)
            })
        return True