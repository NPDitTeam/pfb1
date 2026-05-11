# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _
from odoo.tools import pycompat


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    branch_id = fields.Many2one('res.branch', string='Branch') 
    
    @api.model 
    def default_get(self, flds): 
        """ Override to get default branch from employee """
        result = super(HrExpense, self).default_get(flds)
        
        employee_id = self.env['hr.employee'].search([('user_id','=',self.env.uid)],limit=1)

        if employee_id :
            if employee_id.branch_id :
                result['branch_id'] = employee_id.branch_id.id
        return result 

    @api.onchange('employee_id')
    def get_branch(self):
        if self.employee_id:
            if self.employee_id.branch_id:
                self.update({'branch_id':self.employee_id.branch_id})
            else:
                self.update({'branch_id': False})
                
                
                
        def _create_sheet_from_expenses(self):
            if any(expense.state != 'draft' or expense.sheet_id for expense in self):
                raise UserError(_("You cannot report twice the same line!"))
            if len(self.mapped('employee_id')) != 1:
                raise UserError(_("You cannot report expenses for different employees in the same report."))
            if any(not expense.product_id for expense in self):
                raise UserError(_("You can not create report without product."))
    
            todo = self.filtered(lambda x: x.payment_mode=='own_account') or self.filtered(lambda x: x.payment_mode=='company_account')
            sheet = self.env['hr.expense.sheet'].create({
                'company_id': self.company_id.id,
                'employee_id': self[0].employee_id.id,
                'name': todo[0].name if len(todo) == 1 else '',
                'expense_line_ids': [(6, 0, todo.ids)],
                'branch_id' : self.branch_id.id or False,
            })
            return sheet
                
                
                
    def _prepare_move_values(self):
        """
        This function prepares move values related to an expense
        """
        self.ensure_one()
        journal = self.sheet_id.bank_journal_id if self.payment_mode == 'company_account' else self.sheet_id.journal_id
        account_date = self.sheet_id.accounting_date or self.date
        move_values = {
            'journal_id': journal.id,
            'company_id': self.sheet_id.company_id.id,
            'date': account_date,
            'ref': self.sheet_id.name,
            # force the name to the default value, to avoid an eventual 'default_name' in the context
            # to set it to '' which cause no number to be given to the account.move when posted.
            'name': '/',
            'branch_id' : self.sheet_id.branch_id.id,
        }
        return move_values
    
    
    
    