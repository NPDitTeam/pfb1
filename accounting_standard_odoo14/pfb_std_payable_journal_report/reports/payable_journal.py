from odoo import api,fields, models
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pytz import timezone
import pytz

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def get_journal_id(self,conditions):
        for condition in conditions:
            if condition[0] == 'journal_id':
                return condition[2]
        return None

    def get_dates(self,conditions):
        dates = []
        for condition in conditions:
            if condition[0] == 'date':
                dates.append(condition[2])

        return dates or []

    def date_to_thai(self, input_date_string):

        date_converted = datetime.strptime(input_date_string, '%Y-%m-%d')
        date_converted = date_converted + relativedelta(years=543)

        print('date_converted',date_converted)
        user = self.env['res.users'].browse(self._uid)
        if user.tz:
            tz = pytz.timezone(user.tz) or pytz.utc
            localize_datetime = pytz.utc.localize(date_converted).astimezone(tz)
        else:
            localize_datetime = date_converted
        localize_datetime = localize_datetime.strftime("%d/%m/%Y")

        print('localize_datetime',localize_datetime)
        return localize_datetime

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        year = datetime.now().strftime('%Y') 

        date_start = year + '-01-01'
        date_end = year + '-12-31'
        count = domain.count('&')

        list_domain = []
        for d in domain:
            if d not in ('&','|'):
                list_domain.append(d)

        journal_name = self.get_journal_id(list_domain)
        dates = self.get_dates(list_domain) or []

        period = ''
        if len(dates) >= 1:
            date_start = dates[0]
            period_start = datetime.strptime(date_start, "%Y-%m-%d").month
            period = '%s' % (period_start)
        if len(dates) == 2:
            date_end = dates[1]
            period_start = datetime.strptime(date_start, "%Y-%m-%d").month
            period_end = datetime.strptime(date_end, "%Y-%m-%d").month
            period = '%s - %s' % (period_start, period_end)

        temp = self.env['report.search.move.line.temp'].search([("user_id", "=", self.env.uid)], limit=1)
        
        
        if len(temp):
            temp.unlink()
        idx = self.env['report.search.move.line.temp'].create({
            'journal_name': journal_name,
            'date_start': self.date_to_thai(date_start),
            'date_end': self.date_to_thai(date_end),
            'user_id': self.env.user.id or False,
            'period': period,
        })

        return super().search_read(domain, fields, offset, limit, order)

class report_search_stock_temp(models.Model):
    _name = 'report.search.move.line.temp'

    period = fields.Char(
        string='งวด'
    )
    date_start = fields.Char(
        string='เริ่ม'
    )
    date_end = fields.Char(
        string="ถึง"
    )
    journal_name = fields.Char()
    user_id = fields.Many2one(
        'res.users',
        string="User"
    )

class AccountMoveLinePrint(models.AbstractModel):
    _name = 'report.pfb_std_payable_journal_report.line'

    @api.model
    def _get_report_values(self, docids, data=None):

        docs = self.env['account.move.line'].browse(docids)
        docs = docs.sorted(lambda m: (m.move_id,m.credit))

        move_ids = []
        tmp_move_id = ""
        for d in docs:
            if tmp_move_id != d.move_id.id:
                move_ids.append(d.move_id)
                tmp_move_id = d.move_id.id

        move_id = self.env['account.move.line'].browse(docids)
        report = self.env['ir.actions.report']._get_report_from_name('pfb_std_payable_journal_report.line')
        date_start = ''
        temp = self.env['report.search.move.line.temp'].search([("user_id", "=", self.env.uid)],limit=1)

        
        if temp:
            date_start = temp.date_start
            date_end = temp.date_end
            journal_name = temp.journal_name
            period = temp.period
            if period == '' :
               period = '01-12'
        journal_name = move_id.journal_id.name
        return {
            'period': period,
            'journal_name': journal_name,
            'doc_ids': move_ids,
            'date_start': date_start,
            'date_end': date_end,
            'doc_model': report.model,
            'docs': docs,
            'company_name': docs.company_id.name
        }

