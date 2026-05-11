from odoo import SUPERUSER_ID
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

class PosConfig(models.Model):
    _inherit = 'pos.config'

    is_sequence=fields.Boolean(string="Allow Custom Sequence",readonly=False)
    prefix=fields.Char(string="Prefix")

class PosSession(models.Model):
    _inherit="pos.session"

    prefix=fields.Char(string="Prefix",default="New",readonly=True)
    address=fields.Char(string="Address",readonly=True)
    logo=fields.Binary(string="logo")
    contact_address=fields.Char(string="Address",readonly=True)
    phone=fields.Char(string="phone",readonly=True)
    vat=fields.Char(string="vat",readonly=True)
    email=fields.Char(string="email",readonly=True)
    website=fields.Char(string="website",readonly=True)
    com_name=fields.Char(string="Company name")
    

    @api.model
    def create(self,vals):
        res = super(PosSession, self).create(vals)
       
        for session in res:
            if res.branch_id.prefix:
                session.prefix=res.branch_id.prefix
            else:
                session.prefix=' '

            if session.config_id.is_sequence:
                session.config_id.sequence_id.prefix=session.prefix+"/"

            else:
                session.config_id.sequence_id.prefix=session.config_id.name+"/"

        res.address=res.branch_id.address
        res.logo=res.branch_id.branch_logo
        res.contact_address = res.branch_id.company_id.street
        res.phone = res.branch_id.telephone
        res.vat = res.branch_id.company_id.vat
        res.email = res.branch_id.company_id.email
        res.website = res.branch_id.company_id.website
        res.com_name = res.branch_id.company_id.name
        return res


class PosOrderReport(models.Model):
    _inherit = "report.pos.order"

    prefix=fields.Char(string="Prefix")

    def _select(self):
        return super(PosOrderReport, self)._select() + ",ps.prefix as prefix"


    def _group_by(self):
        return super(PosOrderReport, self)._group_by() + ", ps.prefix"

