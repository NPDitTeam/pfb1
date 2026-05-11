import calendar
import logging
from datetime import date
from functools import reduce
from sys import exc_info
from traceback import format_exception

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)

READONLY_STATES = {
    "submitted": [("readonly", True)],
    "approve": [("readonly", True)],
    "done": [("readonly", True)],
}
class AssetTransfer(models.Model):
    _inherit = 'account.asset'

    # transferred_asset_ids = fields.One2many('std.account.asset.transfer', 'transferred_asset_id',string='Assets')
    asset_owner_id = fields.Many2one('hr.employee', string='Asset Owner')

    def open_asset_transfer(self):
        self.ensure_one()
        context = dict(self.env.context)
        return {
            "name": _("Transfer"),
            "view_mode": "tree,form",
            "res_model": "std.account.asset.transfer",
            "view_id": False,
            "type": "ir.actions.act_window",
            "context": context,
             "domain": [("transferred_asset_ids", "=", self.id)],
        }

class AccountAsset_transfer_type(models.Model):
    _name = "std.account.asset.transfer.type"
    _description = "Asset Transfer Type"

    code = fields.Char(
        string="Code",
        required=True,
    )
    name = fields.Char(
        string="Asset Name",
        required=True,
    )

class AccountAssetTransfer(models.Model):
    _name = "std.account.asset.transfer"
    _inherit = ['mail.thread']
    _description = "Asset Transfer"
    # _order = "date_start desc, code, name"

    transferred_asset_ids = fields.Many2many(
        "account.asset",
        "asset_transfer_rel",
        "transfer_id",
        "asset_id",
        string="Assets to be Transferred",
        help="Assets to be Transferred",
        states=READONLY_STATES,
    )

    asset_transfer_type_id = fields.Many2one(
        comodel_name="std.account.asset.transfer.type",
        string="Transfer Type",
        help="Transfer Type",
        states=READONLY_STATES,
    )
    transferred_date = fields.Date(
        string="Transfer Date",
        states=READONLY_STATES,
    )
    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
        default=lambda self: self._get_my_department(),
    )    
    name = fields.Char(
        string="Asset Name",
        required=True,
        states=READONLY_STATES,
    )
    source_department_id = fields.Many2one(
        comodel_name="stock.location",
        domain="[('usage', '=', 'internal')]",
        string="Source Location",
        help="Source Location",
        states=READONLY_STATES,
    )
    destination_department_id = fields.Many2one(
        comodel_name="stock.location",
        domain="[('usage', '=', 'internal')]",
        string="Destination Location",
        help="Destination Location",
        states=READONLY_STATES,
    )
    source_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Destination",
        help="Destination",
        states=READONLY_STATES,
    )
    received_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Received By",
        help="Received By",
        states=READONLY_STATES,
    )
    destination_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Custodian",
        help="Custodian",
        states=READONLY_STATES,
    )
    reson = fields.Text(
        string="Reson",
        states=READONLY_STATES,
    )
    internal_note = fields.Text(
        string="Internal Note",
        states=READONLY_STATES,
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
        help="When an asset is created, the status is 'Draft'.\n"
        "If the asset is confirmed, the status goes in 'Running' "
        "and the depreciation lines can be posted "
        "to the accounting.\n"
        "If the last depreciation line is posted, "
        "the asset goes into the 'Close' status.\n"
        "When the removal entries are generated, "
        "the asset goes into the 'Removed' status.",
    )
    approved_date = fields.Date('Approved Date', help="Date the asset was finished. ", readonly=True)
    approved_user_id = fields.Many2one('res.users', string='Approved by', readonly=True)
    asset_owner_id = fields.Many2one('hr.employee', string='Asset Owner')

    def _get_my_department(self):
        employees = self.env.user.employee_ids
        return (
            employees[0].department_id
            if employees
            else self.env["hr.department"] or False
        )
    def act_submitted(self):
        return self.write({"state": "submitted"})

    def act_approve(self):
        return self.write({"state": "approve"})

    def act_cancel(self):
        return self.write({"state": "cancel"})

    def act_done(self):

        for asset in self.transferred_asset_ids:
            asset.write({
                "std_location_id": self.destination_department_id.id,
                "std_employee_id": self.asset_owner_id.id
            })

        return self.write({"state": "done",
                           'approved_date': fields.Date.today(),
                           "approved_user_id": self.env.context['uid'],
                           "received_user_id": self.env.context['uid']})

    def act_cancel_officer(self):
        return self.write({"state": "cancel"})

    def act_cancel_manager(self):
        return self.write({"state": "cancel"})

    def act_reset_draft(self):
        return self.write({"state": "draft"})

