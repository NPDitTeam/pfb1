from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tests.common import Form
from odoo.exceptions import UserError

class StockPackingRecreate(models.Model):
    _inherit = "stock.picking"

    std_is_check_create_asset = fields.Boolean('Is Create Assets', compute='_compute_is_check_create_asset')

    def _compute_is_check_create_asset(self, date=False):

        for move in self:
            qty = 0
            if move.state == 'done':
                for aml in move.move_line_ids_without_package.filtered("asset_profile_id"):
                    qty += aml.qty_done
                    print('qty-1--->', qty)

                for aml in move.move_ids_without_package.filtered("asset_profile_id"):
                    qty += aml.product_uom_qty
                    print('qty-2--->', qty)

                asset = self.env["account.asset"].search([("code", "=", move.name)])
                print('asset', len(asset))
                # print('qty', qty)

                if len(asset) < qty and self.is_locked == True:
                    move.std_is_check_create_asset = True
                else:
                    move.std_is_check_create_asset = False

        print('std_is_check_create_asset', self.std_is_check_create_asset)

    def action_create_asset(self):
        self._action_create_asset()

        return True

    def _action_create_asset(self):
        for move in self:
            for aml in move.move_line_ids_without_package.filtered("asset_profile_id"):
                depreciation_base = 0
                qty = aml.qty_done
                i = 0
                while i < qty:
                    vals = {
                        "name": aml.product_id.name,
                        "code": move.name,
                        "profile_id": aml.asset_profile_id,
                        "purchase_value": depreciation_base,
                        "date_start": move.date_done or fields.Date.today(),
                    }
                    if self.env.context.get("company_id"):
                        vals["company_id"] = self.env["res.company"].browse(
                            self.env.context["company_id"]
                        )
                    asset_form = Form(
                        self.env["account.asset"].with_context(
                            create_asset_from_move_line=True
                        )
                    )
                    for key, val in vals.items():
                        setattr(asset_form, key, val)
                    asset = asset_form.save()
                    if aml.asset_group_id:
                        asset.write({"group_ids": [aml.asset_group_id.id]})
                    i += 1
            for aml in move.move_ids_without_package.filtered("asset_profile_id"):
                depreciation_base = 0
                qty = aml.product_uom_qty
                i = 0
                while i < qty:
                    vals = {
                        "name": aml.product_id.name,
                        "code": move.name,
                        "profile_id": aml.asset_profile_id,
                        "purchase_value": depreciation_base,
                        "date_start": move.date_done or fields.Date.today(),
                    }
                    if self.env.context.get("company_id"):
                        vals["company_id"] = self.env["res.company"].browse(
                            self.env.context["company_id"]
                        )
                    asset_form = Form(
                        self.env["account.asset"].with_context(
                            create_asset_from_move_line=True
                        )
                    )
                    for key, val in vals.items():
                        setattr(asset_form, key, val)
                    asset = asset_form.save()
                    if aml.asset_group_id:
                        asset.write({"group_ids": [aml.asset_group_id.id]})
                    i += 1


# class AccountAssetStock(models.Model):
#     _inherit = "account.asset"
#
#     def create(self,value):
#         print(self._context)
#         print(self.context)
#         # {'lang': 'th_TH', 'tz': 'Asia/Bangkok', 'uid': 2, 'allowed_company_ids': [1],
#         #  'params': {'action': 358, 'active_id': 210, 'cids': 1, 'id': 149, 'menu_id': 203, 'model': 'stock.picking',
#         #             'view_type': 'form'}, 'contact_display': 'partner_address', 'active_model': 'stock.picking',
#         #  'active_id': 210, 'active_ids': [210], 'default_company_id': 1, 'keep_line_sequence': True,
#         #  'button_validate_picking_ids': [152], 'default_show_transfers': False, 'default_pick_ids': [[4, 152]],
#         #  'skip_backorder': True, 'picking_ids_not_to_backorder': [152], 'cancel_backorder': True,
#         #  'create_asset_from_move_line': True}
#         if self._context.get('active_model') == 'stock.picking':
#
#
#
#         raise UserError(
#             _(
#                 "The duration of the asset conflicts with the "
#                 "posted depreciation table entry dates."
#             )
#         )
#         res = super(AccountAssetStock, self).create(value)
#
#         return res

