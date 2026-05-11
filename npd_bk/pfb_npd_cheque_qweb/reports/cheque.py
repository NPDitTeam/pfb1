from odoo import api, models
from bahttext import bahttext


class ChequeForm(models.AbstractModel):
    _name = 'report.pfb_npd_cheque_qweb.cheque_pdf_report_pdf'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.cheque'].browse(docids)
        thaibahttext = ''
        type = ''
        for doc in docs:
            thaibahttext = bahttext(doc.cheque_total)
            if doc.format_type == 'ac_bank':
                type = 'ขีดคร่อมเข้าบัญชี'
            elif doc.format_type == 'ac_payee':
                type = 'A/C Payee Only'
            else:
                type = '&CO'
        return {
            'doc_ids': docs.ids,
            'doc_model': 'account.cheque',
            'docs': docs,
            'type': type,
            'thaibahttext': thaibahttext,
        }
