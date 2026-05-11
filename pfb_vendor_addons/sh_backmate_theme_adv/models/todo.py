# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from email.policy import default
from odoo import models,fields, api

class Todo(models.Model):
    _name = "sh.todo"
    _description = "To Do"
    _order = "user_id,is_done,sequence"
    
    name = fields.Char("Name")
    description = fields.Text("Description",default="")
    is_done = fields.Boolean("Done")
    sequence = fields.Integer("Sequence",default=10)
    user_id = fields.Many2one("res.users",string="User",default=lambda self: self.env.uid)

    # @api.model
    # def create_todo(self, vals):
    #     todo_rec = self.create({'name':vals.get('name')})
    #     return {'name': todo_rec.name}
 
    # def write_search(self, vals):
        
    #     self.write({'is_done':vals.get('is_done')})
    #     print("LLLLLLLLLL",self, self.is_done)
    #     data = self.search([('user_id','=',self.env.uid)])
    #     data_list = []
    #     print("\n\ndata",data)
    #     if data:
    #         for rec in data:
               
    #             vals = {
    #                 'id'             : rec.id,
    #                 'name'           : rec.name,
    #                 'description'      : rec.description,
    #                 'is_done' :rec.is_done,
    #                 'user_id':rec.user_id.id
    #                 }
    #             data_list.append(vals)
    #     return  data_list        

    #     return data
