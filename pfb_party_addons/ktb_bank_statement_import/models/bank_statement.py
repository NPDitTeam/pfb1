# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import tempfile
import binascii
import logging
import pandas as pd
from datetime import datetime
from odoo.exceptions import Warning, ValidationError
from odoo import models, fields, api, exceptions, _


_logger = logging.getLogger(__name__)
from io import StringIO
import io
import re

try:
    import csv
except ImportError:
    _logger.debug('Cannot `import csv`.')
try:
    import xlwt
except ImportError:
    _logger.debug('Cannot `import xlwt`.')
try:
    import cStringIO
except ImportError:
    _logger.debug('Cannot `import cStringIO`.')
try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')

try:
    import xlrd
except ImportError:
    _logger.debug('Cannot `import xlrd`.')


class account_bank_statement_wizard(models.TransientModel):
    _name = "account.bank.statement.wizard"
    _description = "Account Bank Statement Wizard"

    file = fields.Binary('File')
    file_opt = fields.Selection([('csv', 'CSV')],default='csv')

    def make_bank_date(self, date):
        DATETIME_FORMAT = "%d%m%Y"
        if date:
            try:
                i_date = datetime.strptime(date, DATETIME_FORMAT).date()
            except Exception:
                raise ValidationError(_('Wrong Date Format. Date Should be in format YYYY-MM-DD.'))
            return i_date
        else:
            raise ValidationError(_('Date field is blank in sheet Please add the date.'))

    def check_splcharacter(self, test):
        # Make own character set and pass
        # this as argument in compile method

        string_check = re.compile('@')

        # Pass the string in search
        # method of regex object.
        if (string_check.search(str(test)) == None):
            return False
        else:
            return True

    def import_file(self):
        if self.file_opt == 'csv':
            try:
                keys = ['Payment Date', 'Ref 2', 'Customer Name', 'memo', 'Amount', 'currency']
                data = base64.b64decode(self.file)
                file_input = io.StringIO(data.decode("utf-8"))

                file_input.seek(0)
                reader_info = pd.read_csv(file_input,skiprows=2,skipfooter=2).to_dict(orient='records')
                import pprint
                pprint.pprint(reader_info)
            except Exception:
                raise ValidationError(_("Not a valid file!"))
            for rec in reader_info:
                account_bank_statement_line_obj = self.env['account.bank.statement.line']
                customer_name = "%s %s" % (rec['Customer Name'].split()[1], rec['Customer Name'].split()[2])
                partner_id = self._find_partner(customer_name)
                currency_id = self._find_currency('THB')
                if not rec['Payment Date']:
                    raise ValidationError('Please Provide Date Field Value')

                date = self.make_bank_date(str(rec['Payment Date']))
                vals = {
                    'date': date,
                    'payment_ref': rec['Customer No./Ref 1'],
                    'ref': rec['Ref 2'],
                    'partner_id': partner_id,
                    'narration': " ".join(rec['Customer Name'].split()),
                    'amount': rec['Amount'],
                    'currency_id': currency_id,
                    'statement_id': self._context.get('active_id'),
                }
                bank_statement_lines = account_bank_statement_line_obj.create(vals)

        # self.env['account.bank.statement'].browse(self._context.get('active_id'))._end_balance()
        return True



    def _find_partner(self, name):
        partner_id = self.env['res.partner'].search([('name', '=', name)])
        if partner_id:
            return partner_id.id
        else:
            return False

    def _find_currency(self, currency):
        currency_id = self.env['res.currency'].search([('name', '=', currency)])
        print(">>>>>>",currency_id)
        if currency_id:
            return currency_id.id
        # else:
        #     raise ValidationError(_(' "%s" Currency are not available.') % currency.decode("utf-8"))


