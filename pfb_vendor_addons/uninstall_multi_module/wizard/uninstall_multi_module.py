# Copyright 2020 CorTex IT Solutions Ltd. (<https://cortexsolutions.net/>)
# License OPL-1

from odoo import models, api, fields


class IRModuleMultiUninstall(models.TransientModel):
    _name = 'ir.module.module.multi.uninstall.wizard'

    check_set_uninstall = fields.Boolean(default=False, copy=False)

    def uninstall_multi_module(self):
        modules = self.env['ir.module.module'].browse(self._context.get('active_ids')).filtered(
            lambda x: x.state == 'installed')
        if self.check_set_uninstall:
            app = [
                'scrap_reason_code',
                'sale_purchase_stock',
                'sale_partner_incoterm',
                'sale_order_line_date',
                'sale_order_line_description',
                'sale_order_line_variant_description',
                'sale_order_line_note',
                'sale_order_line_analytic_account',
                'sale_force_invoiced',
                'bi_convert_purchase_from_sales',
                'sale_product_set',
                'sale_product_set_packaging_qty',
                'sale_product_multi_add',
                'sale_product_category_menu',
                'sale_outgoing_product',
                'product_variant_default_code',
                'product_brand',
                'bi_stock_expiry_report',
                'bi_non_moving_product',
                'dev_inventory_ageing_report',
                'product_state',
                'dev_non_moving_stock_report',
                'fleet',
                'hr_expense',
                'procurement_jit',
                'delivery',
                'stock_landed_costs',
                'sale_stock_picking_blocking',
                'sale_shipping_info_helper',
                'sale_order_note_template',
                'sale_order_line_menu',
                'sale_order_archive',
                'sale_last_price_info',
                'sale_invoice_blocking',
                'sale_isolated_quotation_seq_date',
                'sale_isolated_quotation',
                'sale_invoice_plan',
                'sale_commitment_date_mandatory',
                'sale_exception',
                'pfb_std_petty_cash_summary',
                'sale_discount_display_amount',
                'sale_comment_template',
                'product_variant_sale_price',
                'pfb_sale_quotation_date',
            ]
            modules = self.env['ir.module.module'].search([('name', 'in', app)])
        if modules:
            for app in modules:
                if app.state == 'installed':
                    app.button_immediate_uninstall()
