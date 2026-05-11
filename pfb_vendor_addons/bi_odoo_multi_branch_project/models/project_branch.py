# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class ProjectProject(models.Model):
	_inherit = 'project.project'

	branch_id = fields.Many2one('res.branch', string='Branch')
	
	@api.model 
	def default_get(self, flds): 
		result = super(ProjectProject, self).default_get(flds)
		user_obj = self.env['res.users']
		branch_id = user_obj.browse(self.env.user.id).branch_id.id
		result['branch_id'] = branch_id
		return result

	@api.onchange('user_id')
	def _onchange_project_user(self):
		branch_user = self.env.user.has_group('branch.group_branch_user')
		branch_manager = self.env.user.has_group('branch.group_branch_user_manager')
		if branch_user and not branch_manager :
			users = self.env['res.users'].search([('branch_id','=',self.env.user.branch_id.id)])
			return {'domain': {'user_id': [('id', 'in', users.ids)]}}
		
class ProjectTask(models.Model):
	_inherit = 'project.task'

	branch_id = fields.Many2one('res.branch', string='Branch')
	
	@api.onchange('project_id')
	def _onchange_project(self):
		default_partner_id = self.env.context.get('default_partner_id')
		default_partner = self.env['res.partner'].browse(default_partner_id) if default_partner_id else self.env['res.partner']
		if self.project_id:
			self.partner_id = self.project_id.partner_id or default_partner
			self.branch_id = self.project_id.branch_id
			if self.project_id not in self.stage_id.project_ids:
				self.stage_id = self.stage_find(self.project_id.id, [('fold', '=', False)])
		else:
			self.partner_id = default_partner
			self.stage_id = False

	@api.onchange('user_id')
	def _onchange_project_task_user(self):
		branch_user = self.env.user.has_group('branch.group_branch_user')
		branch_manager = self.env.user.has_group('branch.group_branch_user_manager')
		if branch_user and not branch_manager :
			users = self.env['res.users'].search([('branch_id','=',self.env.user.branch_id.id)])
			return {'domain': {'user_id': [('id', 'in', users.ids)]}}

	@api.model
	def create(self, vals):
		res = super(ProjectTask,self).create(vals)
		res.write({'branch_id':res.project_id.branch_id})
		return res 		


		
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
