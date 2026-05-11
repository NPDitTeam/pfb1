# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import models,fields,api
from odoo.http import request
from operator import itemgetter


class Lang(models.Model):
    _inherit = "res.lang"
    
    @api.model
    def sh_get_installed_lang(self):
        """ Return the installed languages as a list of (code, name) sorted by name. """
        langs = self.with_context(active_test=True).search([])
        return sorted([(lang.code, lang.name, lang.flag_image_url) for lang in langs], key=itemgetter(1))




class sh_wqm_quick_menu(models.Model):
    _name = "sh.wqm.quick.menu"
    _description = "quick / Shortcut menu model"
    _order = "id desc"
    
    # menu_id = fields.Many2one(comodel_name = "ir.ui.menu",
    #                           string = "Menu",
    #                           ondelete='cascade')
    user_id = fields.Many2one(comodel_name = "res.users",
                              string = "User",
                              required = True,
                              ondelete='cascade')
    
    parent_menu_id = fields.Integer(string = "Parent Menu ID")
    
    sh_url = fields.Char("Url ")
    view_type = fields.Char("View Type")
    cids = fields.Char("Cids")
    rec_id = fields.Char("ID")
    model = fields.Char("Model")
    action_id = fields.Char("Action")
    active_id = fields.Char("Active_id")
    name = fields.Char("Name")
    menu_id = fields.Char("Menu")


    @api.model
    def get_search_result(self,query):
        search_quick_menu = self.sudo().search([
            ('name', 'ilike', query[0].lower()),
            ('user_id', '=', self.env.uid)
            ])
        final_quick_menu_list = []
        if search_quick_menu:
            for rec in search_quick_menu:
                type = 'other'
                if rec.sh_url and  len(rec.sh_url.split("view_type=")) >1:
                    type = rec.sh_url.split("view_type=")[1]
                    if len(type.split("&")) > 1:
                        type = type.split("&")[0]

                vals = {
                    'id'             : rec.id,
                    'name'           : rec.name,
                    'sh_url'      : rec.sh_url,
                    'type' :type
                    }
                final_quick_menu_list.append(vals)
                
        return final_quick_menu_list

    def prepare_result(self):
        final_quick_menu_list = []
        search_quick_menu = self.sudo().search([
                ('user_id', '=', self.env.user.id),
                ])
        if search_quick_menu:
            for rec in search_quick_menu:
                type = 'other'
                if rec.sh_url and  len(rec.sh_url.split("view_type=")) >1:
                    type = rec.sh_url.split("view_type=")[1]
                    if len(type.split("&")) > 1:
                        type = type.split("&")[0]
                vals = {
                    'id'             : rec.id,
                    'name'           : rec.name,
                    'sh_url'      : rec.sh_url,
                    'type' :type
                    }
                final_quick_menu_list.append(vals)
        return  final_quick_menu_list        
    

    def set_quick_menu(self, action_id,parent_menu_id):
        if action_id:
            menu = self.env['ir.ui.menu'].sudo().search([('action', 'like', '%,' + str(action_id))], limit=1)
            if not menu:
                action = self.env['ir.actions.actions'].sudo().browse(int(action_id))
                if action:
                    menu = self.env['ir.ui.menu'].sudo().search([('name', '=', action.name), ('action', '!=', '')], limit=1)

            
            if menu:
                rec = self.sudo().search(
                    [('menu_id', '=', menu.id),
                     ('user_id', '=', self.env.user.id)])
                if (rec):
                    if (rec.sudo().unlink()):
                        return {
                            'is_set_quick_menu': False
                        }
                else:
                    if (menu and menu.action):
                        if (self.sudo().create({
                            'menu_id': menu.id,
                            'user_id': self.env.user.id,
                            'parent_menu_id' : int(parent_menu_id),
                        })):
                            return {
                                'is_set_quick_menu': True
                            }
        return {}
    
    def set_quick_url(self, url, model, res_id, action_id):
        print("\n\n\n set_quick_url",url, model, res_id, action_id)
        bookmark_name = ''
        if model and res_id:
            read_data = self.env[model].sudo().search_read([('id','=',res_id)],[],order='id')
            if len(read_data) > 0:
                if 'name' in read_data[0]:
                    bookmark_name = read_data[0]['name']
                elif 'display_name' in read_data[0]:
                    bookmark_name = read_data[0]['display_name']
                elif 'reference' in read_data[0]:
                    bookmark_name = read_data[0]['reference']
                elif 'id' in read_data[0]:
                    bookmark_name = read_data[0]['id']

            

        elif action_id and model != 'mailbox_inbox':
            action = self.env['ir.actions.act_window'].sudo().browse(int(action_id))
            if action:
                bookmark_name = action.name

        if model == 'mailbox_inbox':
            bookmark_name = 'Discuss'

        if url:
             
            data_list = self.get_data_from_url(url)
            rec = self.sudo().search(
                [
                ('view_type', '=', data_list[3]),
                ('cids', '=', data_list[4]),
                ('model', '=', data_list[2]),
                ('action_id', '=', data_list[0]),
                ('menu_id', '=', data_list[1]),
                ('rec_id', '=', data_list[7]),
                ('active_id','=',data_list[5]),
                 ('user_id', '=', self.env.user.id)])
            if (rec):
                if (rec.sudo().unlink()):
                    final_quick_menu_list = self.prepare_result()
                    return {
                        'is_set_quick_menu': False,
                        'final_quick_menu_list':final_quick_menu_list
                    }
            else:
                if (url):

                   
                    data_list = self.get_data_from_url(url)
                    
                    if (self.sudo().create({
                        'sh_url': url,
                        'name': bookmark_name,
                        'user_id': self.env.user.id,
                        'view_type':data_list[3],
                        'cids':data_list[4],
                        'rec_id':data_list[7],
                        'model':data_list[2],
                        'action_id':data_list[0],
                        'active_id':data_list[5],
                        'menu_id':data_list[1]
                    })):
                        final_quick_menu_list = self.prepare_result()
                        return {
                            'is_set_quick_menu': True,
                            'final_quick_menu_list':final_quick_menu_list
                        }
        
        return {}

    

    def is_quick_menu_avail_url(self, url):
        if url:
          
            result = self.is_already_have_in_quick_url(url)
            return result    
                    
    def is_already_have_in_quick_menu(self, menu_id):
        menu = self.env['ir.ui.menu'].sudo().browse(int(menu_id))
        if (menu and menu.action):
            rec = self.sudo().search(
                [('menu_id', '=', menu_id),
                 ('user_id', '=', self.env.user.id)])
            if (rec):
                return True
        return False

    def get_data_from_url(self,url):
        data_list = []
        url_action = ''
        if 'action=' in url:
            url_action = url.split("action=")
            if len(url_action) > 1:
                url_action = url_action[1]
                if len(url_action.split('&')) > 1:
                    url_action = url_action.split('&')[0]
                url_action = url_action
        data_list.append(url_action)

        url_menu = ''
        if 'menu_id=' in url:
            url_menu = url.split("menu_id=")
            if len(url_menu) > 1:
                url_menu = url_menu[1]
                if len(url_menu.split('&')) > 1:
                    url_menu = url_menu.split('&')[0]
                url_menu = url_menu
        data_list.append(url_menu)
        url_model = ''
        if 'model=' in url:
            url_model = url.split("model=")
            if len(url_model) > 1:
                url_model = url_model[1]
                if len(url_model.split('&')) > 1:
                    url_model = url_model.split('&')[0]
                
                url_model = url_model
        data_list.append(url_model)

        url_view_type = ''
        if 'view_type=' in url:
            url_view_type = url.split("view_type=")
            if len(url_view_type) > 1:
                url_view_type = url_view_type[1]
                if len(url_view_type.split('&')) > 1:
                    url_view_type = url_view_type.split('&')[0]
                
                url_view_type = url_view_type
        data_list.append(url_view_type)

        url_cids = ''
        if 'cids=' in url:
            url_cids = url.split("cids=")
            if len(url_cids) > 1:
                url_cids = url_cids[1]
                if len(url_cids.split('&')) > 1:
                    url_cids = url_cids.split('&')[0]
                
                url_cids = url_cids
        data_list.append(url_cids)
    


        url_active_id = ''
        if 'active_id=' in url:
            url_active_id = url.split("active_id=")
            if len(url_active_id) > 1:
                url_active_id = url_active_id[1]
                if len(url_active_id.split('&')) > 1:
                    url_active_id = url_active_id.split('&')[0]
                
                url_active_id = url_active_id
        data_list.append(url_active_id)

        url_active_ids = ''
        if 'active_ids=' in url:
            url_active_ids = url.split("active_ids=")
            if len(url_active_ids) > 1:
                url_active_ids = url_active_ids[1]
                if len(url_active_ids.split('&')) > 1:
                    url_active_ids = url_active_ids.split('&')[0]
                
                url_active_ids = url_active_ids
        data_list.append(url_active_ids)
        url_id = ''
        if '&id=' in url:
            url_id = url.split("&id=")
            if len(url_id) > 1:
                url_id = url_id[1]
                if len(url_id.split('&')) > 1:
                    url_id = url_id.split('&')[0]
                
                url_id = url_id
        elif '#id=' in url:
            url_id = url.split("#id=")
            if len(url_id) > 1:
                url_id = url_id[1]
                if len(url_id.split('&')) > 1:
                    url_id = url_id.split('&')[0]
                
                url_id = url_id
        data_list.append(url_id)
        

        return data_list

    def is_already_have_in_quick_url(self, url):        
        if (url):
            data_list = self.get_data_from_url(url)
            rec = self.sudo().search(
                [('view_type', '=', data_list[3]),
                ('rec_id', '=', data_list[7]),
                ('model', '=', data_list[2]),
                ('action_id', '=', data_list[0]),
                ('active_id','=',data_list[5]),
                ('menu_id', '=', data_list[1]),
                 ('user_id', '=', self.env.user.id)])

            print("\n\n\n rec =========>",url,data_list,data_list[7])
            if (rec):
                return True
        return False

    def get_quick_menu_data(self, fields=[]): 
        final_quick_menu_list = self.prepare_result()
        return final_quick_menu_list

    def remove_quick_menu_data(self, menu_id):
        if menu_id:
            rec = self.sudo().search(
                [('id', '=', menu_id),
                 ('user_id', '=', self.env.user.id)])
            if rec:
                json = {
                    'id': rec.id,
                    'name': rec.name,
                    'sh_url': rec.sh_url,
                }
                
                rec.sudo().unlink()
                final_quick_menu_list = self.prepare_result()
                json.update({'final_quick_menu_list':final_quick_menu_list})
                return json
        return False 
    
class res_users(models.Model):
    _inherit = "res.users"
    
    sh_wqm_web_quick_menu_line = fields.One2many(comodel_name="sh.wqm.quick.menu",
                                                inverse_name="user_id",
                                                string = "Quick Menu",
                                                )
    
    sh_enable_one_click = fields.Boolean('One Click Form Edit')
    sh_enable_night_mode = fields.Boolean('Night Mode')
    sh_enable_language_selection = fields.Boolean('Language Selection',default=True)
    sh_enable_zoom = fields.Boolean('Zoom View',default=False)
    sh_enable_calculator_mode = fields.Boolean('Calculator Mode')
    sh_enable_full_screen_mode = fields.Boolean('Full Screen Mode')
    sh_enable_gloabl_search_mode = fields.Boolean('Global Search Mode')
    sh_enable_quick_menu_mode = fields.Boolean('Quick Menu Mode')
    sh_enable_todo_mode  = fields.Boolean("To Do Feature")


    def __init__(self, pool, cr):
        """ Override of __init__ to add access rights on livechat_username
            Access rights are disabled by default, but allowed
            on some specific fields defined in self.SELF_{READ/WRITE}ABLE_FIELDS.
        """
        init_res = super(res_users, self).__init__(pool, cr)
        # duplicate list to avoid modifying the original reference
        type(self).SELF_WRITEABLE_FIELDS = list(self.SELF_WRITEABLE_FIELDS)
        type(self).SELF_WRITEABLE_FIELDS.extend(['sh_enable_one_click'])
        type(self).SELF_WRITEABLE_FIELDS.extend(['sh_enable_night_mode'])
        type(self).SELF_WRITEABLE_FIELDS.extend(['sh_enable_language_selection'])
        type(self).SELF_WRITEABLE_FIELDS.extend(['sh_enable_zoom'])
        type(self).SELF_WRITEABLE_FIELDS.extend(['sh_enable_calculator_mode'])
        type(self).SELF_WRITEABLE_FIELDS.extend(['sh_enable_full_screen_mode'])
        type(self).SELF_WRITEABLE_FIELDS.extend(['sh_enable_gloabl_search_mode'])
        type(self).SELF_WRITEABLE_FIELDS.extend(['sh_enable_quick_menu_mode'])
        type(self).SELF_WRITEABLE_FIELDS.extend(['sh_enable_todo_mode'])
        # duplicate list to avoid modifying the original reference
        type(self).SELF_READABLE_FIELDS = list(self.SELF_READABLE_FIELDS)
        type(self).SELF_READABLE_FIELDS.extend(['sh_enable_one_click'])
        type(self).SELF_READABLE_FIELDS.extend(['sh_enable_night_mode'])
        type(self).SELF_READABLE_FIELDS.extend(['sh_enable_language_selection'])
        type(self).SELF_READABLE_FIELDS.extend(['sh_enable_zoom'])
        type(self).SELF_READABLE_FIELDS.extend(['sh_enable_calculator_mode'])
        type(self).SELF_READABLE_FIELDS.extend(['sh_enable_full_screen_mode'])
        type(self).SELF_READABLE_FIELDS.extend(['sh_enable_gloabl_search_mode'])
        type(self).SELF_READABLE_FIELDS.extend(['sh_enable_quick_menu_mode'])
        type(self).SELF_READABLE_FIELDS.extend(['sh_enable_todo_mode'])
        return init_res


class Http(models.AbstractModel):
    _inherit = 'ir.http'
    
    def session_info(self):
        info = super().session_info()
        user = request.env.user
        info["sh_enable_one_click"] = user.sh_enable_one_click
        info["sh_enable_night_mode"] = user.sh_enable_night_mode
        info["sh_enable_language_selection"] = user.sh_enable_language_selection
        info["sh_enable_zoom"] = user.sh_enable_zoom
        info["sh_enable_calculator_mode"] = user.sh_enable_calculator_mode
        info["sh_enable_full_screen_mode"] = user.sh_enable_full_screen_mode
        info["sh_enable_gloabl_search_mode"] = user.sh_enable_gloabl_search_mode
        info["sh_enable_quick_menu_mode"] = user.sh_enable_quick_menu_mode
        info["sh_enable_todo_mode"] = user.sh_enable_todo_mode
        return info
    

    