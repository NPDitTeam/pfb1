from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
from num2words import num2words
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    date_string_shot = fields.Char(string='Date String Short', readonly=True,
                                   compute='_compute_date_strings')
    date_string_full = fields.Char(string='Date String Full', readonly=True,
                                   compute='_compute_date_strings')
    order_deadline_string_shot = fields.Char(string='Date Deadline String Short', readonly=True,
                                             compute='_compute_date_strings')
    order_deadline_string_full = fields.Char(string='Date Deadline String Full', readonly=True,
                                             compute='_compute_date_strings')
    amount_text = fields.Char(string='Amount in Text', readonly=True,
                              compute='_compute_amount_text')

    date_string_eng_shot = fields.Char(string='Date String Short', readonly=True,
                                       compute='_compute_date_strings')
    date_string_eng_full = fields.Char(string='Date String Full', readonly=True,
                                       compute='_compute_date_strings')
    order_deadline_eng_string_shot = fields.Char(string='Date String Short', readonly=True,
                                                 compute='_compute_date_strings')
    order_deadline_eng_string_full = fields.Char(string='Date String Full', readonly=True,
                                                 compute='_compute_date_strings')

    currency_id = fields.Many2one('res.currency', string='Currency')  # Currency relation
    amount_in_text = fields.Char(string='Amount in Text', readonly=True, compute='_compute_amount_in_text')

    @api.depends('date_order')
    def _compute_date_strings(self):
        for record in self:
            record.date_string_shot = ""
            record.date_string_full = ""
            record.order_deadline_string_shot = ""
            record.order_deadline_string_full = ""
            record.date_string_eng_shot = ""
            record.date_string_eng_full = ""
            record.order_deadline_eng_string_shot = ""
            record.order_deadline_eng_string_full = ""
            if record.order_date:
                # Convert datetime to date
                order_date = fields.Datetime.to_datetime(record.order_date).date()

                # Case 1: Short format date string (DD/MM/YYYY)
                buddhist_year = order_date.year + 543
                record.date_string_shot = order_date.strftime(f'%d/%m/{buddhist_year}')

                # Case 2: Full format with Thai month and Buddhist year
                thai_months = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน',
                               'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม',
                               'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
                day = order_date.day
                month = thai_months[order_date.month - 1]
                # Adjust year for Buddhist calendar
                year = order_date.year + 543
                record.date_string_full = f"{day} {month} {year}"
                # Case 3: Short format date string (DD/MM/YYYY)
                record.date_string_eng_shot = order_date.strftime(f'%d/%m/%Y')

                # Case 4: Full format with ENG Full month - Corrected
                record.date_string_eng_full = order_date.strftime('%d %B %Y').lstrip('0')
            if record.date_order:
                # Convert datetime to date
                date_order = fields.Datetime.to_datetime(record.date_order).date()

                # Case 1: Short format date string (DD/MM/YYYY)
                buddhist_year = date_order.year + 543
                record.order_deadline_string_shot = date_order.strftime(f'%d/%m/{buddhist_year}')

                # Case 2: Full format with Thai month and Buddhist year
                thai_months = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน',
                               'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม',
                               'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
                day = date_order.day
                month = thai_months[date_order.month - 1]
                # Adjust year for Buddhist calendar
                year = date_order.year + 543
                record.order_deadline_string_full = f"{day} {month} {year}"

                # Case 3: Short format date string (DD/MM/YYYY)
                record.order_deadline_eng_string_shot = date_order.strftime(f'%d/%m/%Y')

                # Case 4: Full format with ENG Full month - Corrected
                record.order_deadline_eng_string_full = date_order.strftime('%d %B %Y').lstrip('0')

    def _compute_amount_text(self):
        for record in self:
            record.amount_text = self._number_to_thai_text(record.amount_total)

    @api.depends('amount_total')
    def _number_to_thai_text(self, amount):
        units = ['', 'สิบ', 'ร้อย', 'พัน', 'หมื่น', 'แสน', 'ล้าน']
        nums = 'ศูนย์ หนึ่ง สอง สาม สี่ ห้า หก เจ็ด แปด เก้า'.split()

        # Split integer and fractional parts
        integer_part, fractional_part = divmod(int(amount * 100), 100)

        if integer_part == 0:
            result = 'ศูนย์บาท'
        else:
            result = ''
            str_amount = str(integer_part)
            length = len(str_amount)
            for i, digit in enumerate(str_amount):
                if digit != '0':
                    if (length - i) == 2 and digit == '1':
                        result += ''
                    elif (length - i) == 2 and digit == '2':
                        result += 'ยี่'
                    elif (length - i) != 1 or digit != '1':
                        result += nums[int(digit)]
                    result += units[length - i - 1]
                elif digit == '0' and (length - i) == 7 and result != '':
                    result += units[length - i - 1]
            result += 'บาท'

        if fractional_part > 0:
            result += self._convert_fractional_part(fractional_part)
        else:
            result += 'ถ้วน'

        return result

    def _convert_fractional_part(self, fractional_part):
        units = ['', 'สิบ']
        nums = 'ศูนย์ หนึ่ง สอง สาม สี่ ห้า หก เจ็ด แปด เก้า'.split()
        result = ''
        str_amount = '{:02d}'.format(fractional_part)
        length = len(str_amount)
        for i, digit in enumerate(str_amount):
            if digit != '0':
                if (length - i) == 2 and digit == '1':
                    result += ''
                elif (length - i) == 2 and digit == '2':
                    result += 'ยี่'
                elif (length - i) != 1 or digit != '1':
                    result += nums[int(digit)]
                result += units[length - i - 1]
        return result + 'สตางค์'

    @api.depends('amount_total', 'currency_id')
    def _compute_amount_in_text(self):
        for record in self:
            if record.currency_id:
                whole_part = int(record.amount_total)
                fractional_part = round((record.amount_total - whole_part) * 100)

                # Use currency_unit_label from the currency_id record
                currency_unit_label = record.currency_id.currency_unit_label if record.currency_id.currency_unit_label else ""

                # Handling for Thai Baht specifically or a default approach
                if record.currency_id.name == 'THB':
                    # Convert the whole part to words for Baht
                    amount_in_words = num2words(whole_part, lang='en').capitalize() if whole_part else "Zero"

                    if fractional_part > 0:
                        # Assuming you have a field for the fractional unit label, e.g., "Satang"
                        fractional_unit_label = "Satang"  # You might want to dynamically fetch this similar to currency_unit_label
                        amount_in_words += " " + currency_unit_label + " and " + num2words(fractional_part,
                                                                                           lang='en') + " " + fractional_unit_label
                    else:
                        # Append "Only" if there are no fractional parts
                        amount_in_words += " " + currency_unit_label + " Only"
                else:
                    # For other currencies, append "Only" without specific handling for fractional units
                    amount_in_words = num2words(record.amount_total,
                                                lang='en').capitalize() + " " + currency_unit_label

                record.amount_in_text = amount_in_words


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    date_planned_string_shot = fields.Char(string='Date Planned String Short', readonly=True,
                                           compute='_compute_date_strings')
    date_planned_string_full = fields.Char(string='Date Planned String Full', readonly=True,
                                           compute='_compute_date_strings')
    date_planned_eng_string_shot = fields.Char(string='Date Planned String Short', readonly=True,
                                               compute='_compute_date_strings')
    date_planned_eng_string_full = fields.Char(string='Date Planned String Full', readonly=True,
                                               compute='_compute_date_strings')
    subtotal_tax = fields.Float(
        string='Subtotal with Tax',
        compute='_compute_subtotal_tax',
        store=True  # Consider if you need to store this computed field
    )

    @api.depends('date_planned')
    def _compute_date_strings(self):
        for record in self:
            if record.date_planned:
                # Convert datetime to date
                date_planned = fields.Datetime.to_datetime(record.date_planned).date()

                # Case 1: Short format date string (DD/MM/YYYY)
                buddhist_year = date_planned.year + 543
                record.date_planned_string_shot = date_planned.strftime(f'%d/%m/{buddhist_year}')

                # Case 2: Full format with Thai month and Buddhist year
                thai_months = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน',
                               'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม',
                               'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม']
                day = date_planned.day
                month = thai_months[date_planned.month - 1]
                # Adjust year for Buddhist calendar
                year = date_planned.year + 543
                record.date_planned_string_full = f"{day} {month} {year}"

                # Case 3: Short format date string (DD/MM/YYYY)
                record.date_string_eng_shot = date_planned.strftime(f'%d/%m/%Y')

                # Case 4: Full format with ENG Full month - Corrected
                record.date_string_eng_full = date_planned.strftime('%d %B %Y').lstrip('0')
            else:
                record.date_planned_string_shot = ""
                record.date_planned_string_full = ""
                record.date_planned_eng_string_shot = ""
                record.date_planned_eng_string_full = ""

    @api.depends('price_subtotal', 'price_tax')
    def _compute_subtotal_tax(self):
        logging.info('--domain----> %r' % (self._fields))
        for record in self:
            if record.price_subtotal:
                # Initialize subtotal_tax to 0 if either field is not set
                record.subtotal_tax = (record.price_subtotal or 0.0) + (record.price_tax or 0.0)
