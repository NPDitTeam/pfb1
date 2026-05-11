from odoo import api, models, _


class KspPaymentVoucherQweb(models.AbstractModel):
    _name = 'report.npd_npd_advance_clear_print.ksp_advance_clear_pdf'
    _description = 'KSP Advance Clear Print'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('npd_npd_advance_clear_print.ksp_advance_clear_pdf')
        records = self.env['account.advance.clear'].browse(docids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }
