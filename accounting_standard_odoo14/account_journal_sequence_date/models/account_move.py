from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    sequence_generated = fields.Boolean(string="Sequence Generated", copy=False)

    @api.depends('posted_before', 'state', 'journal_id', 'date')
    def _compute_name(self):
        for move in self:
            print(move.journal_id.sequence_id.name)
            if not move.journal_id.sequence_id:
              return super(AccountMove, self)._compute_name()
            sequence_id = move._get_sequence()
            print("sequence_id",sequence_id)
            if not sequence_id:
                raise UserError('Please define a sequence on your journal.')
            if not move.sequence_generated and move.state == 'draft':
                move.name = '/'
            elif not move.sequence_generated and move.state != 'draft':
                move.name = sequence_id.next_by_id(sequence_date=move.date)
                move.sequence_generated = True