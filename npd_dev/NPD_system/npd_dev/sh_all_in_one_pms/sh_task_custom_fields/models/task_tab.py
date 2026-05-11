# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import fields,models,api,_
import xml.etree.ElementTree as xee
from odoo.exceptions import UserError
  
class ShCustomModelTask(models.Model):
    _name = 'sh.custom.tab.task'
    _description='Custom Tab task'
    
    @api.model      
    def get_tab_list(self):
        view_id = self.env.ref('project.view_task_form2')
        view_ids = self.env['ir.ui.view'].search([('inherit_id','=',view_id.id)])
        
        data1 = str(view_id.arch_base)
        doc = xee.fromstring(data1)
        tab_list = []
        for tag in doc.findall('.//page'):  
            if 'name' in tag.attrib:
                tab_list.insert(len(tab_list),(tag.attrib['name'], tag.attrib['string']))
        if view_ids:
            for view in view_ids:
                if view != self.view_id:
                    data1 = str(view.arch_base)
                    doc = xee.fromstring(data1)
                    for tag in doc.findall('.//page'):  
                        if 'name' in tag.attrib:
                            tab_list.insert(len(tab_list),(tag.attrib['name'], tag.attrib['string']))
        return tab_list
    
    @api.depends('tab_list')
    def check_invisible_tab(self):
        for rec in self:
            if len(rec.get_tab_list()) >0 :
                rec.invisible_tab = False
            else:
                rec.invisible_tab = True
        
    name = fields.Char("Name")
    label = fields.Char("Label")
    groups = fields.Many2many("res.groups",string="Groups")
    sequence = fields.Integer("Sequence")
    view_id = fields.Many2one('ir.ui.view',string="View")
    tab_list = fields.Selection(selection=get_tab_list,string="Tab List")
    invisible_tab = fields.Boolean("Tab Invisible",compute='check_invisible_tab')
    sh_position = fields.Selection([('before', 'Before'),('after', 'After')],string='Position')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The name must be unique !')
    ]
    
    def unlink(self):
        if self.view_id:
            self.view_id.unlink()
        res = super(ShCustomModelTask, self).unlink()
        return res
    
    def write(self, vals):
        inherit_id = self.env.ref('project.view_task_form2')
        res = super(ShCustomModelTask, self).write(vals)
        
        for rec in self:
            if rec.view_id:
#                 raise UserError("Related View not Found.")
                groups_obj = self.env['res.groups'].search([])
                grp_str = ''
                
                cnt = 0
                for res_grp in groups_obj:
                    for fld_grp in self.groups:
                        dict = fld_grp.get_external_id()
         
                        for k,v in dict.items():              
                            if res_grp.id == k:
                                if cnt == 0:
                                    grp_str += v
                                else :
                                    grp_str += ',' + str(v)
                                cnt += 1
                if rec.tab_list :   
                    if not rec.sh_position:
                        raise UserError("Please Select Position.")
                    
                    if grp_str:
                        arch_base = _('<?xml version="1.0"?>'
                                  '<data>'
                                  '<xpath expr="//form/sheet/notebook/page[@name=\'%s\']" position="%s">'
                                  '<page name="%s" groups="%s"  string="%s"><group></group></page>'
                                  '</xpath>'
                                  '</data>') % (rec.tab_list ,rec.sh_position,rec.name,grp_str,rec.label)
                    else:
                        arch_base = _('<?xml version="1.0"?>'
                                      '<data>'
                                      '<xpath expr="//form/sheet/notebook/page[@name=\'%s\']" position="%s">'
                                      '<page name="%s" string="%s"><group></group></page>'
                                      '</xpath>'
                                      '</data>') % (rec.tab_list ,rec.sh_position,rec.name,rec.label)
                else:
                    if grp_str:
                        arch_base = _('<?xml version="1.0"?>'
                                  '<data>'
                                  '<xpath expr="//form/sheet/notebook" position="inside">'
                                  '<page name="%s" groups="%s"  string="%s"><group></group></page>'
                                  '</xpath>'
                                  '</data>') % (rec.name,grp_str,rec.label)
                    else:
                        arch_base = _('<?xml version="1.0"?>'
                                      '<data>'
                                      '<xpath expr="//form/sheet/notebook" position="inside">'
                                      '<page name="%s" string="%s"><group></group></page>'
                                      '</xpath>'
                                      '</data>') % (rec.name,rec.label)
           
                                  
                rec.view_id.write({'name': 'task.dynamic.tab',
                                      'type': 'form',
                                      'model': 'project.task',
                                      'mode': 'extension',
                                      'inherit_id': inherit_id.id,
                                      'arch_base': arch_base,
                                      'active': True
                                        })
        return res
        
    def create_tab(self):
        
 
        inherit_id = self.env.ref('project.view_task_form2')
        
        groups_obj = self.env['res.groups'].search([])
        grp_str = ''
        
        cnt = 0
        for res_grp in groups_obj:
            for fld_grp in self.groups:
                dict = fld_grp.get_external_id()
 
                for k,v in dict.items():              
                    if res_grp.id == k:
                        if cnt == 0:
                            grp_str += v
                        else :
                            grp_str += ',' + str(v)
                        cnt += 1
        if self.tab_list :   
            if not self.sh_position:
                raise UserError("Please Select Position.")
            
            if grp_str:
                arch_base = _('<?xml version="1.0"?>'
                          '<data>'
                          '<xpath expr="//form/sheet/notebook/page[@name=\'%s\']" position="%s">'
                          '<page name="%s" groups="%s"  string="%s"><group></group></page>'
                          '</xpath>'
                          '</data>') % (self.tab_list ,self.sh_position,self.name,grp_str,self.label)
            else:
                arch_base = _('<?xml version="1.0"?>'
                              '<data>'
                              '<xpath expr="//form/sheet/notebook/page[@name=\'%s\']" position="%s">'
                              '<page name="%s" string="%s"><group></group></page>'
                              '</xpath>'
                              '</data>') % (self.tab_list ,self.sh_position,self.name,self.label)
   
        else:
            if grp_str:
                arch_base = _('<?xml version="1.0"?>'
                          '<data>'
                          '<xpath expr="//form/sheet/notebook" position="inside">'
                          '<page name="%s" groups="%s"  string="%s"><group></group></page>'
                          '</xpath>'
                          '</data>') % (self.name,grp_str,self.label)
            else:
                arch_base = _('<?xml version="1.0"?>'
                              '<data>'
                              '<xpath expr="//form/sheet/notebook" position="inside">'
                              '<page name="%s" string="%s"><group></group></page>'
                              '</xpath>'
                              '</data>') % (self.name,self.label)
    
        ir_ui_view_obj = self.env['ir.ui.view'].create({'name': 'task.dynamic.tab',
                                              'type': 'form',
                                              'model': 'project.task',
                                              'mode': 'extension',
                                              'inherit_id': inherit_id.id,
                                              'arch_base': arch_base,
                                              'active': True
                                    }) 
        self.write({'view_id':ir_ui_view_obj.id})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }            