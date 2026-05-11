# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError



    
class CrossoveredBudgetLines(models.Model):
    _inherit = "crossovered.budget.lines"
    _description = "Budget Line"


    @api.model 
    def default_get(self, field): 
        result = super(CrossoveredBudgetLines, self).default_get(field)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result
    

    branch_id = fields.Many2one( 'res.branch', related='crossovered_budget_id.branch_id', string='Branch', store=True)
    
    
    def _compute_practical_amount(self):
        for line in self:
            if line.branch_id:
                result = 0.0
                acc_ids = line.general_budget_id.account_ids.ids
                date_to = self.env.context.get('wizard_date_to') or line.date_to
                date_from = self.env.context.get('wizard_date_from') or line.date_from
                if not date_to and not date_from:
                    raise ValidationError(_('Please select period first!!!'))
    
                if line.analytic_account_id.id:
                    self.env.cr.execute("""
                        SELECT SUM(amount)
                        FROM account_analytic_line
                        WHERE account_id=%s
                            AND branch_id=%s
                            AND (date between to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd') AND to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd'))
                            AND general_account_id=ANY(%s)""",
                    (line.analytic_account_id.id, line.crossovered_budget_id.branch_id.id, date_from, date_to, acc_ids,))
                    result = self.env.cr.fetchone()[0] or 0.0
                else:
                    self.env.cr.execute("""
                        SELECT sum(credit)-sum(debit)
                        FROM account_move_line
                        WHERE account_id =ANY(%s)
                            AND branch_id=%s 
                            AND (date between to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd') AND to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd'))""",
    
                    (line.general_budget_id.account_ids.ids, line.branch_id.id, date_from, date_to))
                    result = self.env.cr.fetchone()[0] or 0.0
            else:
                result = 0.0
                acc_ids = line.general_budget_id.account_ids.ids
                date_to = self.env.context.get('wizard_date_to') or line.date_to
                date_from = self.env.context.get('wizard_date_from') or line.date_from
                if not date_to and not date_from:
                    raise ValidationError(_('Please select period first!!!'))
    
                if line.analytic_account_id.id:
                    self.env.cr.execute("""
                        SELECT SUM(amount)
                        FROM account_analytic_line
                        WHERE account_id=%s
                            AND (date between to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd') AND to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd'))
                            AND general_account_id=ANY(%s)""",
                    (line.analytic_account_id.id, date_from, date_to, acc_ids,))
                    result = self.env.cr.fetchone()[0] or 0.0
                else:
                    self.env.cr.execute("""
                        SELECT sum(credit)-sum(debit)
                        FROM account_move_line
                        WHERE account_id =ANY(%s)
                            AND (date between to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd') AND to_date(to_char(%s,'yyyy-mm-dd'), 'yyyy-mm-dd'))""",
    
                    (line.general_budget_id.account_ids.ids, date_from, date_to))
                    result = self.env.cr.fetchone()[0] or 0.0
            
            line.practical_amount = result


