# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

class assetRequestStage(models.Model):
    """ Model for case stages. This models the main stages of a asset Request management flow. """
    _name = 'asset.request.stage'
    _description = 'asset Request Stage'
    _order = 'sequence, id'

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=20)
    fold = fields.Boolean('Folded in asset Pipe')
    done = fields.Boolean('Request Done')

class assetRequest(models.Model):
    _name = 'asset.request'
    _inherit = ['mail.thread']
    _description = 'Asset Requests'
    _order = "id desc"

    @api.returns('self')
    def _default_stage(self):
        return self.env['asset.request.stage'].search([], limit=1)

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'stage_id' in init_values and self.stage_id.sequence <= 1:
            return self.env.ref('pfb_std_account_asset_borrow.mt_req_created')
        elif 'stage_id' in init_values and self.stage_id.sequence > 1:
            return self.env.ref('pfb_std_account_asset_borrow.mt_req_status')
        return super(assetRequest, self)._track_subtype(init_values)

    name = fields.Char('Subjects', required=True)
    description = fields.Html('Description')
    request_date = fields.Date('Request Date', track_visibility='onchange', default=fields.Date.context_today,
                               help="Date requested for the asset to happen")
    owner_user_id = fields.Many2one('res.users', string='Created by', default=lambda s: s.env.uid)
    equipment_id = fields.Many2one('account.asset', string='Asset', index=True)
    technician_user_id = fields.Many2one('res.users', string='Owner', track_visibility='onchange', oldname='user_id')
    stage_id = fields.Many2one('asset.request.stage', string='Stage', track_visibility='onchange',
                               group_expand='_read_group_stage_ids', default=_default_stage)
    priority = fields.Selection([('0', 'Very Low'), ('1', 'Low'), ('2', 'Normal'), ('3', 'High')], string='Priority')
    color = fields.Integer('Color Index')
    close_date = fields.Date('Close Date', help="Date the asset was finished. ")
    kanban_state = fields.Selection([('normal', 'In Progress'), ('blocked', 'Cancelled'), ('done', 'Approved')],
                                    string='Kanban State', required=True, default='normal', track_visibility='onchange')
    archive = fields.Boolean(default=False, help="Set archive to true to hide the asset request without deleting it.")
    asset_type = fields.Selection([('corrective', 'Corrective'), ('preventive', 'Preventive')], string='asset Type', default="corrective")
    schedule_date = fields.Datetime('Scheduled Date', help="Date the asset team plans the asset.  It should not differ much from the Request Date. ")
    duration = fields.Float(help="Duration in minutes and seconds.")
    start_date = fields.Date('Start Date', default=fields.Date.context_today)
    end_date = fields.Date('End Date', default=fields.Date.context_today)

    def archive_equipment_request(self):
        self.write({'archive': True})

    def reset_equipment_request(self):
        """ Reinsert the asset request into the asset pipe in the first stage"""
        first_stage_obj = self.env['asset.stage'].search([], order="sequence asc", limit=1)
        # self.write({'active': True, 'stage_id': first_stage_obj.id})
        self.write({'archive': False, 'stage_id': first_stage_obj.id})

    @api.onchange('equipment_id')
    def onchange_equipment_id(self):
        if self.equipment_id:
            if (self.equipment_id.owner_user_id):
                self.equipment_id = None
                return {
                    'warning': {
                        'title': 'Invalid value',
                        'message': 'This Asset had been owned by other.'
                    }
                }

        # if self.equipment_id:
        #     self.technician_user_id = self.equipment_id.technician_user_id if self.equipment_id.technician_user_id else self.equipment_id.category_id.technician_user_id
        #     self.category_id = self.equipment_id.category_id
        #     if self.equipment_id.asset_team_id:
        #         self.asset_team_id = self.equipment_id.asset_team_id.id

    # @api.onchange('category_id')
    # def onchange_category_id(self):
    #     if not self.technician_user_id or not self.equipment_id or (self.technician_user_id and not self.equipment_id.technician_user_id):
    #         self.technician_user_id = self.category_id.technician_user_id
    #
    # @api.model
    # def create(self, vals):
    #     # context: no_log, because subtype already handle this
    #     self = self.with_context(mail_create_nolog=True)
    #     request = super(assetRequest, self).create(vals)
    #     if request.owner_user_id:
    #         request.message_subscribe(partner_ids=[request.owner_user_id.partner_id.id])
    #     if request.equipment_id and not request.asset_team_id:
    #         request.asset_team_id = request.equipment_id.asset_team_id
    #     return request
    #
    #
    def write(self, vals):
        # Overridden to reset the kanban_state to normal whenever
        # the stage (stage_id) of the asset Request changes.
        if vals and 'kanban_state' not in vals and 'stage_id' in vals:
            vals['kanban_state'] = 'normal'
        if vals.get('owner_user_id'):
            owner_user = self.env['res.users'].sudo().browse(vals['owner_user_id'])
            self.message_subscribe(partner_ids=[owner_user.partner_id.id])
        res = super(assetRequest, self).write(vals)
        if self.stage_id.done and 'stage_id' in vals:
            self.write({'close_date': fields.Date.today()})

        if vals and 'kanban_state' in vals :
            if(vals.get('kanban_state') == 'done'):
                if self.stage_id.id == 2:
                    self.change_own(self.equipment_id.id,self.owner_user_id )
                elif self.stage_id.id == 3:
                    self.change_own(self.equipment_id.id,None )
        return res
    #
    def change_own(self, equipment_id , owner_user):
        equipment = self.env['account.asset'].browse(equipment_id)

        if(owner_user == None):
            owner_user_id = None
        else:
            owner_user_id = owner_user.id
        equipment.write({'owner_user_id': owner_user_id})

        # for child_equipment in equipment.asset_child:
        #     child_equipment.write({'owner_user_id': owner_user_id})

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """ Read group customization in order to display all the stages in the
            kanban view, even if they are empty
        """
        stage_ids = stages._search([], order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)

