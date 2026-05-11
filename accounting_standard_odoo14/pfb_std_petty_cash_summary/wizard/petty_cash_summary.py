from odoo import _, api, fields, models


class PettyCashSummary(models.TransientModel):
    _name = "petty.cash.summary"
    _description = "Petty Cash Expense"

    date_range_id = fields.Many2one(
        comodel_name='date.range',
        string='Date range'
    )

    start_date = fields.Date(
        string="Start Date",
        default=fields.Date.today,
        required=True,
        help="",
    )
    end_date = fields.Date(
        string="End Date",
        default=fields.Date.today,
        required=True,
        help="",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True)

    petty_cash_id = fields.Many2one(
        comodel_name='petty.cash',
        string='Petty Name',
        required=True)
    user_id = fields.Many2one("res.users", string="User", index=True, default=lambda self: self.env.user)

    @api.onchange('date_range_id')
    def onchange_date_range_id(self):
        """Handle date range change."""
        if self.date_range_id:
            self.start_date = self.date_range_id.date_start
            self.end_date = self.date_range_id.date_end

    # @api.model
    def create_report_summery(self):
        rows = self.env['petty.cash.summary.rows'].search([])
        rows.unlink()
        expense_ids = self.env['petty.cash.expense'].search([
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date),
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'approve'),
            ('petty_cash_id','=', self.petty_cash_id.id)
        ])
        print('expense_ids',expense_ids)

        for expense in expense_ids:

            self.env['petty.cash.summary.rows'].create({
                'petty_cash_id': self.petty_cash_id.id,
                'expense_name': expense.expense_name,
                'user_id': expense.user_id.id,
                'date': expense.date,
                'total': expense.amount_total,
                'company_id':  self.company_id.id,
                'employee_id': expense.employee_id.id,
                'wht_amount': expense.amount_wht,
                'note': expense.note,
                'state': expense.state,
                'amount': expense.amount,
            })

        return {
            "name": _("Petty Cash Summary"),
            "view_mode": "tree",
            "res_model": "petty.cash.summary.rows",
            "view_id": False,
            "type": "ir.actions.act_window",
            # "context": context,
            # "domain": [("transferred_asset_ids", "=", self.id)],
        }


    # def asset_compute(self):
    #     assets = self.env["account.asset"].search([("state", "=", "open")])
    #     created_move_ids, error_log = assets._compute_entries(
    #         self.date_end, check_triggers=True
    #     )
    #
    #     if error_log:
    #         module = __name__.split("addons.")[1].split(".")[0]
    #         result_view = self.env.ref(
    #             "{}.{}_view_form_result".format(module, self._table)
    #         )
    #         self.note = _("Compute Assets errors") + ":\n" + error_log
    #         return {
    #             "name": _("Compute Assets result"),
    #             "res_id": self.id,
    #             "view_mode": "form",
    #             "res_model": "account.asset.compute",
    #             "view_id": result_view.id,
    #             "target": "new",
    #             "type": "ir.actions.act_window",
    #             "context": {"asset_move_ids": created_move_ids},
    #         }
    #
    #     return {
    #         "name": _("Created Asset Moves"),
    #         "view_mode": "tree,form",
    #         "res_model": "account.move",
    #         "view_id": False,
    #         "domain": [("id", "in", created_move_ids)],
    #         "type": "ir.actions.act_window",
    #     }

    def view_asset_moves(self):
        self.ensure_one()
        domain = [("id", "in", self.env.context.get("asset_move_ids", []))]
        return {
            "name": _("Created Asset Moves"),
            "view_mode": "tree,form",
            "res_model": "account.move",
            "view_id": False,
            "domain": domain,
            "type": "ir.actions.act_window",
        }
