from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tests.common import Form
from datetime import datetime, timedelta


class StockPacking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        super(StockPacking, self)._action_done()
        for move in self:
<<<<<<< HEAD
            for aml in move.move_line_ids_without_package.filtered("asset_profile_id"):
                depreciation_base = 0
                qty = aml.qty_done
=======
<<<<<<< HEAD
            for aml in move.move_line_ids_without_package.filtered("asset_profile_id"):
                depreciation_base = 0
                qty = aml.qty_done
=======
            # for aml in move.move_line_ids_without_package.filtered("asset_profile_id"):
            #     depreciation_base = 0
            #     qty = aml.qty_done
            #     i = 0
            #     po_id = ''
            #     po_date = ''
            #     po_price = 0
            #     if aml.move_id.purchase_line_id:
            #         po_id = aml.move_id.purchase_line_id.order_id.id
            #         po_date = aml.move_id.purchase_line_id.order_id.order_date
            #         po_price = aml.move_id.purchase_line_id.price_total / aml.move_id.purchase_line_id.product_qty
            #         aml.aml_price_unit = aml.move_id.purchase_line_id.price_unit
            #     while i < qty:
            #         vals = {
            #             "name": aml.product_id.name,
            #             "code": move.name,
            #             "profile_id": aml.asset_profile_id,
            #             "purchase_value": depreciation_base,
            #             "date_start": move.date_done or fields.Date.today(),
            #             "std_purchase_date": po_date or False,
            #         }
            #         if self.env.context.get("company_id"):
            #             vals["company_id"] = self.env["res.company"].browse(
            #                 self.env.context["company_id"]
            #             )
            #         asset_form = Form(
            #             self.env["account.asset"].with_context(
            #                 create_asset_from_move_line=True
            #             )
            #         )
            #         for key, val in vals.items():
            #             setattr(asset_form, key, val)
            #         asset = asset_form.save()
            #         if aml.asset_group_id:
            #             asset.write({"group_ids": [aml.asset_group_id.id]})
            #         asset.write({
            #             "std_asset_purchase_id": po_id or False,
            #             "std_purchase_price": po_price or 0,
            #         })
            #         params = self.env['ir.config_parameter'].sudo()
            #         asset_below_threshold = params.get_param('pfb_std_account_asset_voucher.asset_below_threshold') or 0
            #         asset_below_threshold = float(asset_below_threshold)
            #         if asset_below_threshold != 0:
            #             if po_price < asset_below_threshold:
            #                 asset.write({
            #                     "purchase_value": 0,
            #                     "purchase_paid_value": 0,
            #                     'date_start': datetime.now(),
            #                     'std_no_compute_asset': True
            #                 })
            #
            #             if po_price > asset_below_threshold:
            #                 asset.write({
            #                     "purchase_value": po_price,
            #                     "purchase_paid_value": po_price,
            #                     'date_start': datetime.now(),
            #                     'std_no_compute_asset': False
            #                 })
            #         if aml.warranty_date_end:
            #             self.env["account.asset.insurance"].create(
            #                 {
            #                     'insurance_id': asset.id,
            #                     'end_of_warranty': aml.warranty_date_end
            #                 })
            #         i += 1
            for aml in move.move_ids_without_package.filtered("asset_profile_id"):
                depreciation_base = 0
                qty = aml.product_uom_qty
>>>>>>> a0b03d924c5ff5e2348f3414e9c30301593aab1a
>>>>>>> 87f83c7ee0c7235f075d1fdcb5a6c594e769643e
                i = 0
                po_id = ''
                po_date = ''
                po_price = 0
<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 87f83c7ee0c7235f075d1fdcb5a6c594e769643e
                if aml.move_id.purchase_line_id:
                    po_id = aml.move_id.purchase_line_id.order_id.id
                    po_date = aml.move_id.purchase_line_id.order_id.order_date
                    po_price = aml.move_id.purchase_line_id.price_total / aml.move_id.purchase_line_id.product_qty
                    aml.aml_price_unit = aml.move_id.purchase_line_id.price_unit
<<<<<<< HEAD
=======
=======
                if aml.purchase_line_id:
                    po_id = aml.purchase_line_id.order_id.id
                    po_date = aml.purchase_line_id.order_id.order_date
                    po_price = aml.purchase_line_id.price_total / aml.purchase_line_id.product_qty
>>>>>>> a0b03d924c5ff5e2348f3414e9c30301593aab1a
>>>>>>> 87f83c7ee0c7235f075d1fdcb5a6c594e769643e
                while i < qty:
                    vals = {
                        "name": aml.product_id.name,
                        "code": move.name,
                        "profile_id": aml.asset_profile_id,
                        "purchase_value": depreciation_base,
                        "date_start": move.date_done or fields.Date.today(),
                        "std_purchase_date": po_date or False,
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
<<<<<<< HEAD
                        asset.write({"group_ids": [aml.asset_group_id.id]})
                    asset.write({
                        "std_asset_purchase_id": po_id or False,
                        "std_purchase_price": po_price or 0,
                    })
=======
<<<<<<< HEAD
                        asset.write({"group_ids": [aml.asset_group_id.id]})
                    asset.write({
                        "std_asset_purchase_id": po_id or False,
                        "std_purchase_price": po_price or 0,
                    })
=======
                        asset.write({"group_ids": [aml.asset_group_id.id],
                                     })
                    asset.write({
                                 "std_asset_purchase_id": po_id or False,
                                 "std_purchase_price": po_price or 0,
                                 })
>>>>>>> a0b03d924c5ff5e2348f3414e9c30301593aab1a
>>>>>>> 87f83c7ee0c7235f075d1fdcb5a6c594e769643e
                    params = self.env['ir.config_parameter'].sudo()
                    asset_below_threshold = params.get_param('pfb_std_account_asset_voucher.asset_below_threshold') or 0
                    asset_below_threshold = float(asset_below_threshold)
                    if asset_below_threshold != 0:
                        if po_price < asset_below_threshold:
                            asset.write({
                                "purchase_value": 0,
                                "purchase_paid_value": 0,
                                'date_start': datetime.now(),
<<<<<<< HEAD
                                'std_no_compute_asset': True,
                                'partner_id': move.partner_id.id
                            })

                        if po_price > asset_below_threshold:
                            asset.write({
                                "purchase_value": po_price,
                                "purchase_paid_value": po_price,
                                'date_start': datetime.now(),
                                'std_no_compute_asset': False,
                                'partner_id': move.partner_id.id
                            })
=======
<<<<<<< HEAD
                                'std_no_compute_asset': True,
                                'partner_id': move.partner_id.id
                            })

                        if po_price > asset_below_threshold:
                            asset.write({
                                "purchase_value": po_price,
                                "purchase_paid_value": po_price,
                                'date_start': datetime.now(),
                                'std_no_compute_asset': False,
                                'partner_id': move.partner_id.id
                            })
=======
                                'std_no_compute_asset': True
                            })

                        # if po_price > asset_below_threshold:
                        #     asset.write({
                        #         "purchase_value": po_price,
                        #         "purchase_paid_value": po_price,
                        #         'date_start': datetime.now(),
                        #         # 'std_no_compute_asset': False
                        #     })
>>>>>>> a0b03d924c5ff5e2348f3414e9c30301593aab1a
>>>>>>> 87f83c7ee0c7235f075d1fdcb5a6c594e769643e
                    if aml.warranty_date_end:
                        self.env["account.asset.insurance"].create(
                            {
                                'insurance_id': asset.id,
                                'end_of_warranty': aml.warranty_date_end
                            })
                    i += 1
            # for aml in move.move_ids_without_package.filtered("asset_profile_id"):
            #     depreciation_base = 0
            #     qty = aml.product_uom_qty
            #     i = 0
            #     po_id = ''
            #     po_date = ''
            #     po_price = 0
            #     if aml.purchase_line_id:
            #         po_id = aml.purchase_line_id.order_id.id
            #         po_date = aml.purchase_line_id.order_id.order_date
            #         po_price = aml.purchase_line_id.price_total / aml.purchase_line_id.product_qty
            #     while i < qty:
            #         vals = {
            #             "name": aml.product_id.name,
            #             "code": move.name,
            #             "profile_id": aml.asset_profile_id,
            #             "purchase_value": depreciation_base,
            #             "date_start": move.date_done or fields.Date.today(),
            #             "std_purchase_date": po_date or False,
            #         }
            #         if self.env.context.get("company_id"):
            #             vals["company_id"] = self.env["res.company"].browse(
            #                 self.env.context["company_id"]
            #             )
            #         asset_form = Form(
            #             self.env["account.asset"].with_context(
            #                 create_asset_from_move_line=True
            #             )
            #         )
            #         for key, val in vals.items():
            #             setattr(asset_form, key, val)
            #         asset = asset_form.save()
            #         if aml.asset_group_id:
            #             asset.write({"group_ids": [aml.asset_group_id.id],
            #                          })
            #         asset.write({
            #                      "std_asset_purchase_id": po_id or False,
            #                      "std_purchase_price": po_price or 0,
            #                      })
            #         if aml.warranty_date_end:
            #             self.env["account.asset.insurance"].create(
            #                 {
            #                     'insurance_id': asset.id,
            #                     'end_of_warranty': aml.warranty_date_end
            #                 })
            #         i += 1
<<<<<<< HEAD
=======

>>>>>>> 87f83c7ee0c7235f075d1fdcb5a6c594e769643e


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    asset_group_id = fields.Many2one(
        comodel_name="account.asset.group",
        string="Asset Group",
        required=False,
    )
    asset_profile_id = fields.Many2one(
        comodel_name="account.asset.profile",
        string="Asset Profile",
        required=False,
    )
    warranty_date_end = fields.Date('End of Warranty')

    aml_price_unit = fields.Float("Unit Price", default=0)


class StockMove(models.Model):
    _inherit = "stock.move"

    asset_group_id = fields.Many2many(
        comodel_name="account.asset.group",
        string="Asset Group",
        related='product_id.asset_profile_id.group_ids',
        required=False,
    )
    asset_profile_id = fields.Many2one(
        comodel_name="account.asset.profile",
        string="Asset Profile",
        required=False,
        related='product_id.asset_profile_id'
    )
    warranty_date_end = fields.Date('End of Warranty')
