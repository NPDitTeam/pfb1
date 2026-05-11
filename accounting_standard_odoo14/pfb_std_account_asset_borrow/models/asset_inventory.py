from datetime import date, datetime, timedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class assetInventoryEquipmentRel(models.Model):
    """ Model for case stages. This models the main stages of a asset Request management flow. """
    
    _name = 'asset.inventory.equipment.rel'
    _description = 'asset Inventory Equipment Rel'
    _order = 'id'

    name = fields.Char('Name')
    inventory_id = fields.Many2one('asset.inventory', 'Inventory')
    equipment_id = fields.Many2one('account.asset', 'Equipment', required=True)
    description = fields.Html('Description')
    state = fields.Selection([('chua_kiem_ke', 'Non-Inventory'), ('du', 'Enough'), ('thieu', 'Not enough')], string='Inventory State',
                                    default="chua_kiem_ke")

    start_date = fields.Date('Start Date', compute='_compute_start_date')
    end_date = fields.Date('End Date', compute='_compute_end_date')


    @api.depends('inventory_id')
    def _compute_start_date(self):
        if(self.inventory_id):
            self.start_date = self.inventory_id.start_date

    @api.depends('inventory_id')
    def _compute_end_date(self):
        if(self.inventory_id):
            self.end_date = self.inventory_id.end_date

class assetInventory(models.Model):
    """ Model for case stages. This models the main stages of a asset Request management flow. """
    _name = 'asset.inventory'
    _description = 'asset Inventory'
    _inherit = ['mail.thread']
    _order = 'id'

    name = fields.Char('Name', required=True)
    user_id = fields.Many2one('res.users', string='Performer', track_visibility='onchange',default=lambda self: self.env.user)
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    description = fields.Html('Description')
    equipment_rel_ids = fields.One2many('asset.inventory.equipment.rel', 'inventory_id')
    # category_id = fields.Many2one('account.asset.category', string='Load equipment from equipment type',track_visibility='onchange')
    inventory_status_da_kiem_ke = fields.Char('Inventory Status Inventoried', compute='_compute_inventory_status')
    inventory_status_chua_kiem_ke = fields.Char('Inventory Status Non-Inventory', compute='_compute_inventory_status')
    inventory_status_du = fields.Char('Inventory Status Enough', compute='_compute_inventory_status')
    inventory_status_thieu = fields.Char('Inventory Status Not-Enough', compute='_compute_inventory_status')
    use_in_location = fields.Many2one('hr.department', string='Department')


    @api.depends('equipment_rel_ids')
    def _compute_inventory_status(self):
        if(self.equipment_rel_ids):
            chua_kiem_ke = 0
            du = 0
            thieu = 0
            for equipment_rel in self.equipment_rel_ids:
                if(equipment_rel.state == 'chua_kiem_ke'):
                    chua_kiem_ke = chua_kiem_ke + 1
                elif(equipment_rel.state == 'du'):
                    du = du + 1
                elif(equipment_rel.state == 'thieu'):
                    thieu = thieu + 1

            self.inventory_status_chua_kiem_ke = str(chua_kiem_ke) + ' / ' + str(len(self.equipment_rel_ids))
            self.inventory_status_da_kiem_ke = str(len(self.equipment_rel_ids) - chua_kiem_ke) + ' / ' + str(len(self.equipment_rel_ids))
            self.inventory_status_du = str(du) + ' / ' + str(len(self.equipment_rel_ids))
            self.inventory_status_thieu = str(thieu) + ' / ' + str(len(self.equipment_rel_ids))

        # else :
        #     # self.inventory_status = '0/0'
        #     self.inventory_status_thieu = ''

    def load_equipment(self):
        # category_id = self.category_id
        use_in_location = 0 #self.use_in_location

        equipment_array = []
        data_search = []
        self.equipment_rel_ids = None
        # if(category_id.id != False):
        #     data_search += [('category_id' , '=' ,category_id.id )]
        if (use_in_location.id != False):
            departmnet_array = self.get_department(use_in_location)
            data_search += [('use_in_location.id', 'in', departmnet_array)]

        equipments = self.env['account.asset'].search(data_search)

        for id in equipments.ids:

            new_rel = (0, 0, {
                'state': 'chua_kiem_ke',
                'equipment_id': id,
            })
            if (new_rel not in equipment_array):
                equipment_array += [new_rel]

        self.equipment_rel_ids = equipment_array
