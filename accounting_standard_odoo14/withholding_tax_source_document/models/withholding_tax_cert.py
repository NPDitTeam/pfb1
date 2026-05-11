from odoo import models, fields, api, _



class WithholdingTaxCert(models.Model):
    _inherit = "withholding.tax.cert"

    source_document = fields.Char(string=_('Source document'),compute="_get_source_document")

    def _get_source_document(self):
        for rec in self:
            if rec.payment_id:
                rec.source_document = rec.payment_id.move_id.name
            elif rec.voucher_id:
                rec.source_document = rec.voucher_id.move_id.name
            elif rec.petty_expense_id:
                rec.source_document = rec.petty_expense_id.move_id.name
            elif rec.move_id:
                rec.source_document = rec.move_id.name
            else:
                rec.source_document = ""
