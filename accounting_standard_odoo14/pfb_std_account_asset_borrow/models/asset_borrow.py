from datetime import date, datetime, timedelta

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class assetBorrowStage(models.Model):
    """ Model for case stages. This models the main stages of a asset Request management flow. """
    _name = 'asset.borrow.stage'
    _description = 'asset Borrow Stage'
    _order = 'sequence, id'

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=20)
    fold = fields.Boolean('Folded in asset Pipe')
    done = fields.Boolean('Request Done')
    borrow_state = fields.Selection([('new', 'New Request'), ('requested', 'Requested'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('returned', 'Returned')], string='Borrow State')

class AccountassetBorrowRequest(models.Model):
    _inherit = 'account.asset'
    # equipment_ids = fields.One2many('asset.borrow.request', 'equipment_id',string='Assets')
    borrow_state = fields.Selection([('available', 'Available'), ('transfering', 'Transfering'),
                                     ('unavailable', 'Unavailable')], string='Borrow State',
                                    default="available")
    owner_user_id = fields.Many2one('res.users', string='Owner', track_visibility='onchange')
    assign_date = fields.Date('Assigned Date', track_visibility='onchange', default=fields.Date.context_today)
    end_date = fields.Date('End Date', default=fields.Date.context_today)
    # borrow_asset_id = fields.Many2one('asset.borrow.request', string='Asset', index=True)

    def open_asset_borrow(self):
        self.ensure_one()
        context = dict(self.env.context)
        return {
            "name": _("Borrow Request"),
            "view_mode": "tree,form",
            "res_model": "asset.borrow.request",
            "view_id": False,
            "type": "ir.actions.act_window",
            "context": context,
             "domain": [("equipment_ids", "=", self.id)],
        }

class assetBorrowRequest(models.Model):
    _name = 'asset.borrow.request'
    _inherit = ['mail.thread']
    _description = 'asset Borrow Requests'
    _order = "id desc"

    @api.returns('self')
    def _default_stage(self):
        return self.env['asset.borrow.stage'].search([], limit=1)

    name = fields.Char('Subjects', required=True)
    description = fields.Html('Description')
    request_date = fields.Date('Request Date', track_visibility='onchange',
                               help="Date requested for the asset to happen" , readonly = True)

    rejected_date = fields.Date('Rejected Date', track_visibility='onchange',
                                help="Date requested for the asset to happen", readonly = True)
    rejected_user_id = fields.Many2one('res.users', string='Rejected by', readonly=True)

    approved_date = fields.Date('Approved Date', help="Date the asset was finished. ", readonly=True)
    approved_user_id = fields.Many2one('res.users', string='Approved by', readonly=True)

    returned_date = fields.Date('Returned Date', track_visibility='onchange',help="Date requested for the asset to happen", readonly=True)
    returned_user_id = fields.Many2one('res.users', string='Returned by', readonly=True)

    owner_user_id = fields.Many2one('res.users', string='Created by', default=lambda s: s.env.uid , readonly = True)
    # equipment_id = fields.Many2one('account.asset', string='Asset', index=True)
    equipment_ids = fields.Many2many('account.asset','asset_borrow_rel', 'equipment_id', 'asset_id', string='Asset', index=True)
    # equipment_ids = fields.One2many('account.asset', 'borrow_asset_id', string='Asset', index=True)
    stage_id = fields.Many2one('asset.borrow.stage', string='Stage', ondelete='restrict', tracking=True,
                               group_expand='_read_group_stage_ids', default=_default_stage, copy=False)
    priority = fields.Selection([('0', 'Very Low'), ('1', 'Low'), ('2', 'Normal'), ('3', 'High')], string='Priority')
    color = fields.Integer('Color Index')
    archive = fields.Boolean(default=False, help="Set archive to true to hide the asset request without deleting it.")
    start_date = fields.Date('Start Date', default=fields.Date.context_today)
    end_date = fields.Date('End Date', default=fields.Date.context_today)
    current_stage_borrow_state = fields.Char(string='Borrow State', compute='_compute_current_stage_borrow_state' , store=True)
    attachment_ids = fields.Many2many('ir.attachment', 'asset_borrow_request_ir_attachments_rel', 'borrow_request_id',
                                      'attachment_id',
                                      'Attachments')
    borrow_type = fields.Selection([('muon', 'Require'), ('dieu_chuyen', 'Transfer')], string='Type')
    description_borrow = fields.Html('Description borrow')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    def _track_subtype(self, init_values):
        self.ensure_one()
        # if 'stage_id' in init_values:
        #     return self.env.ref('account_asset_borrow.mt_borrow_req_status')
        if 'stage_id' in init_values and self.stage_id.borrow_state == 'new':
            return self.env.ref('pfb_std_account_asset_borrow.mt_borrow_req_created') #'account_asset_borrow.mt_borrow_req_created'
        elif 'stage_id' in init_values and self.stage_id.sequence > 1:
            return self.env.ref('pfb_std_account_asset_borrow.mt_borrow_req_status') #return 'account_asset_borrow.mt_borrow_req_status'
        return super(assetBorrowRequest, self)._track_subtype(init_values)

    @api.depends('stage_id')
    def _compute_current_stage_borrow_state(self):
        stage = self.env['asset.borrow.stage'].browse(self.stage_id.id)
        self.current_stage_borrow_state = stage.borrow_state

    def archive_equipment_request(self):
        self.write({'archive': True})

    @api.onchange('stage_id')
    def onchange_stage_id(self):
        if(self.stage_id.borrow_state != 'new' ):
            if not self.equipment_ids:
                self.stage_id = None
                return {
                    'warning': {
                        'title': 'Invalid value',
                        'message': _('Pick a design state')
                    }
                }

    @api.onchange('equipment_ids')
    def onchange_equipment_id(self):
        # self.ensure_one()
        # print(self.equipment_ids)
        # print(self.equipment_ids.owner_user_id)
        # print(self.owner_user_id)
        # print(self.owner_user_id)
        # print(self.equipment_ids.borrow_state)
        # if len(self.equipment_ids.owner_user_id > 0):
        if (self.equipment_ids.owner_user_id == self.owner_user_id):
            self.equipment_ids = None
            return {
                'warning': {
                    'title': 'Invalid value',
                    'message': _('What are you doing today?')
                }
            }

        # if not isinstance(self.equipment_ids.borrow_state, str):
        #     if (self.equipment_ids.borrow_state == 'transfering'):
        #         self.equipment_ids = None
        #         return {
        #             'warning': {
        #                 'title': 'Invalid value',
        #                 'message': _('Someone is borrowing this device')
        #             }
        #         }
        #     elif (self.equipment_ids.borrow_state == 'unavailable'):
        #         self.equipment_ids = None
        #         return {
        #             'warning': {
        #                 'title': 'Invalid value',
        #                 'message': _('There s nothing wrong with that')
        #             }
        #         }

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """ Read group customization in order to display all the stages in the
            kanban view, even if they are empty
        """
        stage_ids = stages._search([], order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)
    
    def reset_equipment_request(self):
        """ Reinsert the asset request into the asset pipe in the first stage"""
        first_stage_obj = self.env['asset.borrow.stage'].search([], order="sequence asc", limit=1)
        # self.write({'active': True, 'stage_id': first_stage_obj.id})
        self.write({'archive': False, 'stage_id': first_stage_obj.id})

    def is_asset_manager(self, user):
        if(user and user.has_group('pfb_std_asset_free_field.group_asset_manager')):
            return True
        else:
            return False

    def is_borrow_request_stage(self, stage_id, borrow_state):
        stage = self.env['asset.borrow.stage'].browse(stage_id)
        return stage.borrow_state == borrow_state


    def is_equipment_transferring(self, equipment_id, transferring_state):
        equipment = self.env['account.asset'].browse(equipment_id)
        return equipment.borrow_state == transferring_state

    # @api.model
    # def create(self, vals):
    #     context = dict(self.env.context)
    #     if 'equipment_id' in vals:
    #         equipment = self.env['sprogroupasset.equipment'].browse(vals.get('equipment_id'))
    #         if (equipment.owner_user_id.id == False):
    #             vals.update({'borrow_type': 'muon'})
    #         else:
    #             vals.update({'borrow_type': 'dieu_chuyen'})
    #     res = super(assetBorrowRequest, self.with_context(context)).create(vals)
    #
    #     return res

    def write(self, vals):

        # current_user = self.env['res.users'].browse(self.env.context['uid'])

        # if ('stage_id' in vals and self.is_borrow_request_stage(vals.get('stage_id'), 'new')):
        #     if (self.equipment_id.borrow_state == 'transfering'):
        #         raise ValidationError(u'Asset are requesting to borrow')
        #         return False
        #
        #     # print(self.stage_id.id)
        #     if (self.is_borrow_request_stage(self.stage_id.id, 'new')):  # check previous stage
        #         go = True
        #     elif (self.is_borrow_request_stage(self.stage_id.id, 'requested')):  # check previous stage
        #         go = True
        #     else:
        #         raise ValidationError(u'You cannot change')
        #         return False
        #
        # if ('stage_id' in vals and self.is_borrow_request_stage(vals.get('stage_id'), 'returned')):
        #     if (not self.is_borrow_request_stage(self.stage_id.id, 'approved')):  # check previous stage
        #         raise ValidationError(u'You cannot change')
        #         return False
        #     if (not self.is_asset_manager(current_user)):
        #         raise ValidationError(u'You cannot change')
        #         return False
        #
        # if ('stage_id' in vals and self.is_borrow_request_stage(vals.get('stage_id'), 'requested')):
        #     if (self.equipment_ids == False):
        #         raise ValidationError(u'Please, Select Asset')
        #         return False
        #
        #
        #     for equipment in self.equipment_ids:
        #         # for equipment_data in self.browse([("equipment_ids", "=", equipment.id)]):
        #         #     print(equipment_data)
        #         if (equipment.borrow_state == 'transfering'):
        #             raise ValidationError(u'Asset are requesting to borrow')
        #             return False
        #
        #     if (not self.is_borrow_request_stage(self.stage_id.id, 'new')):  # check previous stage
        #         raise ValidationError(u'You cannot change')
        #         return False
        #
        #     if (not self.is_asset_manager(current_user) and self.owner_user_id != current_user):
        #         raise ValidationError(u'You cannot change')
        #         return False
        #
        # if ('stage_id' in vals and self.is_borrow_request_stage(vals.get('stage_id'), 'approved')):
        #     if (not self.is_borrow_request_stage(self.stage_id.id, 'requested')):  # check previous stage
        #         raise ValidationError(u'You cannot change')
        #         return False
        #     if (self.archive == True):
        #         raise ValidationError(u'Request has been discarded')
        #         return False
        #     if not self.is_asset_manager(current_user):
        #         for equipment_id in self.equipment_ids:
        #             if equipment_id.owner_user_id != current_user:
        #                 raise ValidationError(u'You cannot change')
        #         return False
        #
        # if ('stage_id' in vals and self.is_borrow_request_stage(vals.get('stage_id'), 'rejected')):
        #     if (not self.is_borrow_request_stage(self.stage_id.id, 'requested')):  # check previous stage
        #         raise ValidationError(u'You cannot change')
        #         return False
        #
        #     if not self.is_asset_manager(current_user):
        #         for equipment_id in self.equipment_ids:
        #             if equipment_id.owner_user_id != current_user:
        #                 raise ValidationError(u'You cannot change')
        #         return False

        res = super(assetBorrowRequest, self).write(vals)

        if (self.archive == True):
            # self.update_equipment(self.equipment_ids, {'borrow_state': 'available'})
            self.equipment_ids.write({'borrow_state': 'available'})
        now = fields.Datetime.now()
        if self.stage_id.borrow_state == 'new' and 'stage_id' in vals:
            # self.equipment_id.write({'borrow_state': 'available'})
            # self.update_equipment(self.equipment_ids, {'borrow_state': 'available'})
            self.equipment_ids.write({'borrow_state': 'available'})
        elif self.stage_id.borrow_state == 'requested' and 'stage_id' in vals:
            self.write({'request_date': fields.Date.today()})
            # self.equipment_id.write({'borrow_state': 'transfering'})
            # self.update_equipment(self.equipment_ids, {'borrow_state': 'transfering'})
            self.equipment_ids.write({'borrow_state': 'transfering'})
        elif self.stage_id.borrow_state == 'approved' and 'stage_id' in vals:
            self.write({'approved_date': fields.Date.today(), 'approved_user_id': self.env.context['uid']})
            is_update = self.equipment_ids.write({'borrow_state': 'available'})
            # is_update = self.update_equipment(self.equipment_ids, {'borrow_state': 'available'})

            if is_update:
                self.change_own(self.equipment_ids, self.owner_user_id)
        elif self.stage_id.borrow_state == 'rejected' and 'stage_id' in vals:
            self.write({'rejected_date': fields.Date.today(), 'rejected_user_id': self.env.context['uid']})
            # self.update_equipment(self.equipment_id.id, {'borrow_state': 'available'})
            self.equipment_ids.write({'borrow_state': 'available'})
        elif self.stage_id.borrow_state == 'returned' and 'stage_id' in vals:
            self.write({'returned_date': fields.Date.today(), 'returned_user_id': self.env.context['uid']})
            is_update = self.equipment_ids.write({'borrow_state': 'available'})
            # is_update = self.update_equipment(self.equipment_id.id, {'borrow_state': 'available'})
            if is_update:
                self.change_own(self.equipment_ids, None)
        return res

    def unlink(self):
        if self.stage_id.borrow_state != 'new':
            raise ValidationError(_('You cannot delete'))
        return super(assetBorrowRequest, self).unlink()

    
    def copy(self, default=None):
        raise ValidationError(_('You cannot copy'))


    def change_own(self, equipment_ids, owner_user):
        equipment = equipment_ids #self.env['account.asset'].browse(equipment_id)
        now = fields.Datetime.now()

        if(owner_user == None):
            owner_user_id = None
            assign_date = None
            end_date = None
        else:
            owner_user_id = owner_user.id
            assign_date = now
            end_date = self.end_date
        equipment.write({'owner_user_id': owner_user_id })
        equipment.write({'assign_date':  assign_date})
        equipment.write({'end_date':  end_date})

