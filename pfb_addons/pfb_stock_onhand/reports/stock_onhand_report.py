# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockOnhandView(models.TransientModel):
    _name = "stock.onhand.view"
    _description = "Stock Onhand View"
    _order = "date"

    # date = fields.Datetime()
    product_id = fields.Many2one(comodel_name="product.product")
    # product_qty = fields.Float()
    # product_uom_qty = fields.Float()
    product_uom = fields.Many2one(comodel_name="uom.uom")
    # reference = fields.Char()
    # location_id = fields.Many2one(comodel_name="stock.location")
    # location_dest_id = fields.Many2one(comodel_name="stock.location")
    # is_initial = fields.Boolean()
    product_in = fields.Float()
    product_out = fields.Float()
    secondary_quantity_in = fields.Float()
    secondary_quantity_out = fields.Float()
    value = fields.Float()
    # secondary_product_uom = fields.Many2one(comodel_name="uom.uom")
    # picking_id = fields.Many2one(comodel_name="stock.picking")
    lot_id = fields.Many2one(comodel_name="stock.production.lot")

    def name_get(self):
        result = []
        for rec in self:
            name = rec.reference
            if rec.picking_id.origin:
                name = "{} ({})".format(name, rec.picking_id.origin)
            result.append((rec.id, name))
        return result


class StockOnhandReport(models.TransientModel):
    _name = "report.stock.onhand.report"
    _description = "Stock On hand Report"

    # Filters fields, used for data computation
    date_from = fields.Date()
    date_to = fields.Date()
    product_ids = fields.Many2many(comodel_name="product.product")
    location_id = fields.Many2one(comodel_name="stock.location")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)

    # Data fields, used to browse report data
    results = fields.Many2many(
        comodel_name="stock.onhand.view",
        compute="_compute_results",
        help="Use compute fields, so there is nothing store in database",
    )

    def _compute_results(self):
        self.ensure_one()
        date_from = self.date_from or "0001-01-01"
        self.date_to = self.date_to or fields.Date.context_today(self)
        locations = self.env["stock.location"].search(
            [("id", "child_of", [self.location_id.id])]
        )
        sql =  """
        SELECT move.product_id,move.lot_id,move.product_uom_id as product_uom,
             sum(case when move.location_dest_id in %s
                    then move.qty_done end) as product_in,
                sum(case when move.location_id in %s
                    then move.qty_done end) as product_out,
            sum(case when move.location_dest_id in %s
                    then move.secondary_done_qty end) as secondary_quantity_in,
                sum(case when move.location_id in %s
                    then move.secondary_done_qty end) as secondary_quantity_out,
                      sum(stock_layer.value/stock_layer.quantity) as value
        FROM stock_move_line move 
        LEFT JOIN stock_valuation_layer stock_layer on move.move_id = stock_layer.stock_move_id
        WHERE (move.location_id in %s or move.location_dest_id in %s)
                and move.state = 'done' and move.product_id in %s
                and CAST(move.date AS date) <= %s
                and move.qty_done > 0
                group by move.product_id,move.lot_id,move.product_uom_id
        """%(
                tuple(locations.ids),
                tuple(locations.ids),
                tuple(locations.ids),
                tuple(locations.ids),
                # date_from,
                tuple(locations.ids),
                tuple(locations.ids),
                tuple(self.product_ids.ids),
                self.date_to,
            )
        print(sql)
        self._cr.execute(
            """
        SELECT move.product_id,move.lot_id,move.product_uom_id as product_uom,
                sum(case when move.location_dest_id in %s
                    then move.qty_done end) as product_in,
                sum(case when move.location_id in %s
                    then move.qty_done end) as product_out,
                sum(case when move.location_dest_id in %s
                    then move.secondary_done_qty end) as secondary_quantity_in,
                sum(case when move.location_id in %s
                    then move.secondary_done_qty end) as secondary_quantity_out,
                sum(stock_layer.value/stock_layer.quantity) as value
        FROM stock_move_line move 
        LEFT JOIN stock_valuation_layer stock_layer on move.move_id = stock_layer.stock_move_id
      
        WHERE (move.location_id in %s or move.location_dest_id in %s)
                and move.state = 'done' and move.product_id in %s
                and CAST(move.date AS date) <= %s
                and move.qty_done > 0
                group by move.product_id,move.lot_id,move.product_uom_id
        """,
            (
                tuple(locations.ids),
                tuple(locations.ids),
                tuple(locations.ids),
                tuple(locations.ids),
                # date_from,
                tuple(locations.ids),
                tuple(locations.ids),
                tuple(self.product_ids.ids),
                self.date_to,
            ),
        )
        stock_card_results = self._cr.dictfetchall()
        ReportLine = self.env["stock.onhand.view"]
        self.results = [ReportLine.new(line).id for line in stock_card_results]

    def _get_initial(self, product_line):
        product_input_qty = sum(product_line.mapped("product_in"))
        product_output_qty = sum(product_line.mapped("product_out"))
        return product_input_qty - product_output_qty

    def print_report(self, report_type="qweb"):
        self.ensure_one()
        action = (
            report_type == "xlsx"
            and self.env.ref("pfb_stock_onhand.action_stock_onhand_report_xlsx")
            or self.env.ref("pfb_stock_onhand.action_stock_onhand_report_pdf")
        )
        return action.report_action(self, config=False)

    def _get_html(self):
        result = {}
        rcontext = {}
        report = self.browse(self._context.get("active_id"))
        if report:
            rcontext["o"] = report
            result["html"] = self.env.ref(
                "pfb_stock_onhand.report_stock_onhand_report_html"
            )._render(rcontext)
        return result

    @api.model
    def get_html(self, given_context=None):
        return self.with_context(given_context)._get_html()


class ProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    picking_id = fields.Many2one('stock.picking', string="Stock Picking", compute='_compute_stock_picking')

    def _compute_stock_picking(self):
        for lot in self:
            move_line = self.env['stock.move.line'].search([('lot_id','=',lot.id)],limit=1,order='id desc')
            lot.picking_id = move_line[0].move_id.picking_id