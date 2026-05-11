# -*- coding: utf-8 -*-


from odoo import api, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class report_asset_card(models.AbstractModel):
    _name = 'report.pfb_std_asset_card_print.report_asset_card'
    _description = 'Report Asset Card'

    @api.model
    def _get_report_values(self, docids, data=None):



        report = self.env['ir.actions.report']._get_report_from_name('pfb_std_asset_card_print.report_asset_card')
        records = self.env['account.asset'].browse(docids)
        # _logger.debug(" docids%s",docids)
        # _logger.debug(" _ids %s", self._ids)

        return {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': records,
            'data': data,

        }

