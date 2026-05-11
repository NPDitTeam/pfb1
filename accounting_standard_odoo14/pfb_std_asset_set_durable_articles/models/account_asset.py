from odoo import fields, models, _, api


class AccountAsset(models.Model):
    _inherit = "account.asset"

    std_asset_line_ids = fields.One2many('std.account.asset.line', 'set_asset_id', string='Assets')


class AccountAssetLine(models.Model):
    _name = "std.account.asset.line"

    def _get_name(self):
        asset_name = self
        name = asset_name.name or ''
        res = []
        print(name)
        if self._context.get('show_asset_name', True):
            print(self._context.get('show_asset_name', True))
            for asset in asset_name.set_asset_id:
                name = asset.name
                res.append(name)
        return res

    set_asset_id = fields.Many2one(
        'account.asset', string='Asset Id'
    )
    std_asset_id = fields.Many2one(
        comodel_name='account.asset', string='Asset Id'
    )
    # std_employee_id = fields.Many2one(
    #     string='Employee',
    #     related='std_asset_id.std_employee_id')

    depreciation_base = fields.Float(
        string="Depreciation Base",
        store=True,
        related='std_asset_id.depreciation_base'
    )

    depreciation_base = fields.Float(
        string="Depreciation Base",
        store=True,
        related='std_asset_id.depreciation_base'
    )

    value_depreciated = fields.Float(
        string="Depreciation Value",
        store=True,
        related='std_asset_id.value_depreciated'
    )

    value_residual = fields.Float(
        string="Residual Value",
        store=True,
        related='std_asset_id.value_residual'
    )
    date_start = fields.Date(
        related='std_asset_id.date_start',
        string="Asset Start Date",
        required=True,
    )
    profile_id = fields.Many2one(
        string="Asset Profile",
        related='std_asset_id.profile_id'
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("open", "Running"),
            ("close", "Close"),
            ("removed", "Removed"),
        ],
        string="Status",
        required=True,
        default="draft",
        copy=False,
        related='std_asset_id.state'
    )
    # group_ids = fields.Many2many(
    #     comodel_name="account.asset.group",
    #     readonly=False,
    #     store=True,
    #     relation="std_asset_id.group_ids",
    #     column1="view_id",
    #     column2="group_id",
    #     string="Asset Groups",
    # )
    #
    # account_analytic_id = fields.Many2one(
    #     comodel_name="account.analytic.account",
    #     string="Analytic account",
    #     readonly=False,
    #     store=True,
    # )
    #
    # purchase_value = fields.Float(
    #     string="Purchase Value",
    #     required=True,
    # )
    #
    # std_condition_remark = fields.Text(string="Remark")
    #
    # state = fields.Selection(
    #     selection=[
    #         ("draft", "Draft"),
    #         ("open", "Running"),
    #         ("close", "Close"),
    #         ("removed", "Removed"),
    #     ],
    #     string="Status",
    #     copy=False,
    # )
