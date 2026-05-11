from odoo import api, fields, models


class AccountJournal(models.Model):
    _name = 'account.journal'
    _inherit = 'account.journal'

    type = fields.Selection([
        ('sale', 'Sales'),
        ('purchase', 'Purchase'),
        ('receivable', 'Receivable'),
        ('payable', 'Payable'),
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('general', 'Miscellaneous'),
    ], required=True)
