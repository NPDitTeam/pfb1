from odoo import fields, models
from odoo.http import request

class ResCompany(models.Model):
    _inherit = "res.company"

    theme_id = fields.Many2one("azk.theme.customization", string="Color Scheme")

    def rpc_ifo_theme(self):
        result = []
        if self.theme_id:
            base_url = request.httprequest.url_root
            link_href_css = "{}web/content/{}".format(base_url, self.theme_id.css_attachment_id.id)
            script_src_js = None
            if self.theme_id.custom_js:
                script_src_js = "{}web/content/{}".format(base_url, self.theme_id.js_attachment_id.id)
            result = [{
                'link_href_css': link_href_css ,
                'script_src_js': script_src_js
                }]
            if self.theme_id.is_add_ribbon:
                result += [{
                    'ribbon_text': self.theme_id.ribbon_text,
                }]
        return result
        
class Config(models.TransientModel):
    _inherit = "res.config.settings"

    theme_id = fields.Many2one(related='company_id.theme_id',readonly=False)
