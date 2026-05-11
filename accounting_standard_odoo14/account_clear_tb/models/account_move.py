# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

class AccountMove(models.Model):
    _inherit = "account.move"

    is_clear_tb = fields.Boolean(
        string="Clear TB",
    )
    clear_tb_move_id = fields.Many2one(
        comodel_name="account.move",
        string="Move Entry Clear TB",
        readonly=True,
        copy=False,
    )
    def button_draft(self):
        super().button_draft()
        if self.clear_tb_move_id:
            self.clear_tb_move_id.button_cancel()

    def action_post(self):
        super().action_post()
        if self.state == 'posted' and self.is_clear_tb and not self.clear_tb_move_id:
            self.clear_tb_move_id = self.revert_entry()
            self.clear_tb_move_id.tax_invoice_ids.with_context(force_remove_tax_invoice=True).sudo().unlink()
        elif self.clear_tb_move_id:
            self.clear_tb_move_id.line_ids.sudo().unlink()
            self.revert_line()
            self.clear_tb_move_id.tax_invoice_ids.with_context(force_remove_tax_invoice=True).sudo().unlink()
            self.clear_tb_move_id.write({'state':'posted'})
        return False
    def revert_line(self, default_values_list=None,cancel=True):
        if not default_values_list:
            default_values_list = [{} for move in self]
        move_vals_list = []
        for move, default_values in zip(self, default_values_list):
            move_vals_list.append(move.with_context(move_reverse_cancel=cancel)._reverse_move_vals(default_values, cancel=cancel))
        self.clear_tb_move_id.update({'line_ids':move_vals_list[0].get('line_ids')})

    def revert_entry(self, default_values_list=None, cancel=True):
        if not default_values_list:
            default_values_list = [{} for move in self]
        if not self.env.company.clear_tb_journal_id:
            raise UserError(_('Please setting Journal Voucher Clear TB'))

        move_vals_list = []
        for move, default_values in zip(self, default_values_list):
            default_values.update({ 
                'move_type': 'entry',
                'reversed_entry_id': move.id,
                'journal_id': self.env.company.clear_tb_journal_id.id,
                'ref': 'Clear Tb %s'%(move.name),
                'invoice_date': move.invoice_date,
            })

            move_vals_list.append(move.with_context(move_reverse_cancel=cancel)._reverse_move_vals(default_values, cancel=cancel))
        
        reverse_moves = self.env['account.move'].create(move_vals_list)
        for move, reverse_move in zip(self, reverse_moves.with_context(check_move_validity=False)):
            # Update amount_currency if the date has changed.
            if move.date != reverse_move.date:
                for line in reverse_move.line_ids:
                    if line.currency_id:
                        line._onchange_currency()
            reverse_move._recompute_dynamic_lines(recompute_all_taxes=False)
        reverse_moves._check_balanced()
        for tax in reverse_moves.tax_invoice_ids:
            tax.tax_invoice_number = reverse_moves.ref
            tax.tax_invoice_date = reverse_moves.date
        # Reconcile moves together to cancel the previous one.
        if cancel:
            reverse_moves.with_context(move_reverse_cancel=cancel)._post(soft=False)
        return reverse_moves