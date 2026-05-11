# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class StockPickingTransportInfo(models.Model):
    _name = 'stock.picking.transport.info'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order= 'id desc'

    name = fields.Char(string='Number', readonly=True)
    state = fields.Selection([('draft', 'Prepration'),('ready','Ready'),('halt', 'Halt'),('done', 'Delivery'),('cancel', 'Cancelled'),('res', 'Rescheduled')],
        default='draft',
        track_visibility='onchange',
        copy=False,
    )
    saleorder_id = fields.Many2one('sale.order',string="Sale Order")
    transporter_id = fields.Many2one('res.partner', string="Transporter", required=True)
    vehicle_id = fields.Many2one('fleet.vehicle',string="Vehicle")
    vehicle_driver = fields.Many2one('transport.driver', string="Driver")
    transport_date = fields.Datetime(string='Shipment Date', required=True, default=fields.Datetime.now())
    delivery_id = fields.Many2one('stock.picking', string='Picking')
    customer_id = fields.Many2one('res.partner', string='Customer')
    destination_id = fields.Many2one('stock.location', string='Destination')
    lr_number = fields.Char(string="LR Number", store=True)
    carrier_id = fields.Many2one('delivery.carrier', string='Carrier')
    carrier_tracking_ref = fields.Char(string='Tracking Ref')
    weight = fields.Float(string='Weight')
    shipping_weight = fields.Float(string='Weight')
    number_of_packages = fields.Integer(string='No of Packages')
    weight_uom_id = fields.Many2one('uom.uom', string='Weight')
    no_of_parcel = fields.Float(string="No of Parcels")
    picking_route_ids = fields.One2many('stock.picking.route', 'delivery_route_id', string='Shipment Route', copy=True)
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user.id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.user.company_id, string='Company', readonly=True)
    note = fields.Text(string='Notes')
    count_route = fields.Integer(string="Route", compute='_compute_count_route')
    o_start = fields.Float(string='Odometer Start')
    o_end = fields.Float(string="Odometer End")
    picking_date = fields.Date(string='Picking Date')
    exp_date = fields.Date(string='Expected Date')
    rate = fields.Float(string='Rate')
    distance = fields.Float(string='Distance')
    total_charge = fields.Float(string='Total Charges', compute='_compute_total_charge')
    bill = fields.Char(string='Waybill No')
    ref_no = fields.Char(string='Reference No')
    
    @api.depends('distance')
    def _compute_total_charge(self):
        for rec in self:
            if rec.distance:
                rec.total_charge = rec.distance*rec.rate
            else:
                rec.total_charge = 0

    def picking_ready(self):
        for rec in self:
            rec.state = 'ready'

    def picking_prepration(self):
        for rec in self:
            rec.state = 'prepration'    

    def picking_hold(self):
        for rec in self:
            rec.state = 'halt'

    def _compute_count_route(self):
        for picking in self:
            picking.count_route = len(picking.picking_route_ids)


    def picking_done(self):
        for rec in self:
            rec.state = 'done'
            rec.picking_route_ids.write({'state': 'reach', 'status': 'reach'})

    def picking_cancel(self):
        for rec in self:
            rec.state = 'cancel'

    def picking_reschedule(self):
        for rec in self:
            reschedule = rec.copy()
            # rec.write({'picking_transport_info_id' : reschedule.id})
            res = self.env.ref('pways_transportor_management.action_picking_transport_info')
            res = res.read()[0]
            res['domain'] = str([('id','=', reschedule.id)])
            rec.state = 'res'
        return res

    @api.model_create_multi
    def create(self, vals):
        for val in vals:
            name = self.env['ir.sequence'].next_by_code('picking.transport.seq')
            val.update({'name': name})
        return super(StockPickingTransportInfo, self).create(vals)

    def unlink(self):
        for rec in self:
            if rec.state != 'cancel':
                raise UserError(_('You can not delete record in this state.'))
        return super(StockPickingTransportInfo, self).unlink()

    def action_open_picking_route(self):
        return {
            'name': _('Picking Routes'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'stock.picking.route',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.picking_route_ids.ids)],
        }
    
    @api.model
    def get_transport_data(self):
        transporter = 0
        total_shipment = 0
        total_draft = 0
        total_ready = 0
        total_halt=0
        total_done=0
        data = {}
        self._cr.execute('''select COUNT(id) from res_partner WHERE res_partner.transporter = '%s'
        ''' % True)
        record = self._cr.dictfetchall()
        rec_ids = [item['count'] for item in record]
        transporter = rec_ids[0]
        data['transporter'] = transporter

        self._cr.execute('''select COUNT(id) from stock_picking_transport_info''')
        record = self._cr.dictfetchall()
        rec_ids = [item['count'] for item in record]
        total_shipment = rec_ids[0]
        data['total_shipment'] = total_shipment

        self._cr.execute('''select COUNT(id) from stock_picking_transport_info WHERE stock_picking_transport_info.state ='draft' ''')
        record = self._cr.dictfetchall()
        rec_ids = [item['count'] for item in record]
        total_draft = rec_ids[0] 
        data['total_draft'] = total_draft

        self._cr.execute('''select COUNT(id) from stock_picking_transport_info WHERE stock_picking_transport_info.state ='ready' ''')
        record = self._cr.dictfetchall()
        rec_ids = [item['count'] for item in record]
        total_ready = rec_ids[0] 
        data['total_ready'] = total_ready

        self._cr.execute('''select COUNT(id) from stock_picking_transport_info WHERE stock_picking_transport_info.state ='halt' ''')
        record = self._cr.dictfetchall()
        rec_ids = [item['count'] for item in record]
        total_halt = rec_ids[0]
        data['total_halt'] = total_halt

        self._cr.execute('''select COUNT(id) from stock_picking_transport_info WHERE stock_picking_transport_info.state ='done' ''')
        record = self._cr.dictfetchall()
        rec_ids = [item['count'] for item in record]
        total_done = rec_ids[0]
        data['total_done'] = total_done
        return data


    @api.model
    def transport_route_data(self):
        activities_ids = self.env['stock.picking.transport.info'].search([])
        transporter_list = []
        transport_dictonary = {}
        for activity in activities_ids:
            if activity.transporter_id not in transport_dictonary:
                transport_dictonary[activity.transporter_id] = activity
            else:
                transport_dictonary[activity.transporter_id] |= activity

        for key, values in transport_dictonary.items():
            for val in values[0]:
                l1 = {"name": val.transporter_id.name, 'id': val.transporter_id.id, 'weight': sum(values.mapped('weight')),  "distance": sum(values.mapped('distance')), 'total': sum(values.mapped('total_charge'))}
                transporter_list.append(l1)
        return transporter_list