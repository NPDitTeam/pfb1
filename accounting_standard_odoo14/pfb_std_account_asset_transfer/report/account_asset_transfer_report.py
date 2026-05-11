
from odoo import tools
from odoo import api, fields, models


class AccountAssetTransfer(models.Model):
    _name = "std.account.asset.transfer.report"
    _auto = False
    _inherit = ['mail.thread']
    _description = "Asset Transfer"
    # _order = "date_start desc, code, name"

    asset_id = fields.Many2one(
        "account.asset",
        string="Assets to be Transferred",
        help="Assets to be Transferred",

    )
    asset_transfer_type_id = fields.Many2one(
        comodel_name="std.account.asset.transfer.type",
        string="Transfer Type",
        help="Transfer Type",
    )
    transferred_date = fields.Date(
        string="Transfer Date",
    )
    name = fields.Char(
        string="Transfer Name",
        required=True,
    )
    source_department_id = fields.Many2one(
        comodel_name="stock.location",
    )
    destination_department_id = fields.Many2one(
        comodel_name="stock.location",
    )

    source_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Destination",
        help="Destination",
    )
    received_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Received By",
        help="Received By",
    )

    destination_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Custodian",
        help="Custodian",
    )

    reson = fields.Text(
        string="Reson",
    )
    internal_note = fields.Text(
        string="Internal Note",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approve", "Approve"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        track_visibility='onchange',
        string="Status",
        required=True,
        default="draft",
        copy=False,
    )
    approved_date = fields.Date('Approved Date', help="Date the asset was finished. ", readonly=True)
    approved_user_id = fields.Many2one('res.users', string='Approved by', readonly=True)
    asset_owner_id = fields.Many2one('hr.employee', string='Asset Owner')
    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
    )    
    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
                CREATE or REPLACE view %s as (
                  select 
                     t.id 
                    ,r.asset_id
                    ,t.asset_transfer_type_id
                    ,t.transferred_date
                    ,t.name
                    ,t.source_department_id
                    ,t.destination_department_id
                    ,t.source_partner_id
                    ,t.received_user_id
                    ,t.destination_partner_id
                    ,t.reson
                    ,t.internal_note
                    ,t.state
                    ,t.approved_date
                    ,t.approved_user_id
                    ,t.asset_owner_id
                    ,t.department_id
                    from std_account_asset_transfer  t
                    LEFT JOIN asset_transfer_rel r ON t.id = r.transfer_id
                );
            """ % self._table)
