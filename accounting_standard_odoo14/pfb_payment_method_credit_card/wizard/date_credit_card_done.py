from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DateCreditCardDone(models.TransientModel):
    _name = "date.credit.card.done"

    date_done = fields.Date('Date Receipt', default=fields.Datetime.now, required=True)

    def action_done_credit_card(self):
        credit_cards = self.env['account.credit.card'].browse(self._context.get('active_ids', []))
        for cq in credit_cards:
            cq.date_receipt = self.date_done
        return True