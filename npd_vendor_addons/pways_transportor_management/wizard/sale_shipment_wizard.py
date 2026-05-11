from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaletShipmentWizard(models.TransientModel):
    _name = 'sale.shipment.wizard'
    _description ="Sale Report"

    route = fields.Many2one('stock.transporter.route' , string='Route', required=True)
    driver = fields.Many2one('transport.driver' , string='Driver' , required=True)
    vehicle = fields.Many2one('fleet.vehicle' , string='Vehicle' ,required=True)
    pick_date = fields.Date(string='Picking Date',required=True)
    arrive_date = fields.Date(string='Arrival Date',required=True)
    picking_type = fields.Many2one('shipment.type', string='Type',required=True)


    def create_transport_record(self):
        model = self.env.context.get('active_model')
        active_id = self.env[model].browse(self.env.context.get('active_id'))
        if not active_id.create_trans:
            active_id.write({
                'transporter_route_id': self.route.id,
                'vehicle_driver': self.driver.id,
                'vehicle_id': self.vehicle.id, 
                'pick_date': self.pick_date,
                'arrive_date':self.arrive_date,
                'picking_type':self.picking_type.id,
                'create_trans': True,
            })
        return True