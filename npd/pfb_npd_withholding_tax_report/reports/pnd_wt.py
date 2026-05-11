from odoo import api, models, fields
from dateutil.relativedelta import relativedelta


class WithholdingTaxCert(models.Model):
    _inherit = "withholding.tax.cert"

    report_late_mo = fields.Char()


class PfbWithholdingReport(models.AbstractModel):
    _name = 'report.pfb_npd_withholding_tax_report.pnd_qweb'

    def year_convert(self, convert_date):
        date_converted = convert_date + relativedelta(years=543)
        date_converted = date_converted.strftime('%d/%m/%Y')
        return date_converted

    def _get_report_values(self, docids, data=None):
        docs = self.env['withholding.tax.cert.line'].browse(docids)
        count = 0
        company = False
        for doc in docs:
            income_tax_form = doc.cert_id
            if doc.company_id:
                company = doc.company_id
            count += len(doc)

            return {
                'doc_ids': docs.ids,
                'doc_model': 'withholding.tax.cert.line',
                'docs': docs,
                'income_tax_form': income_tax_form,
                'company': company,
            }
