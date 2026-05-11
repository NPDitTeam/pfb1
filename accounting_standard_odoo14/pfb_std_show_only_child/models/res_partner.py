from odoo import models, fields, api, _


class ResPartnerPartnerChildName(models.Model):
    _inherit = 'res.partner'

    def name_get(self):
        res = []
        if self._context.get('show_only_child'):
            for partner in self:
                name = partner.name
                res.append((partner.id, name))
        else:
            for partner in self:
                name = partner._get_name()
                res.append((partner.id, name))
        return res
