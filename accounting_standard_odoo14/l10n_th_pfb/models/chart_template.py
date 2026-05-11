# coding: utf-8
# Copyright 2016 iterativo (https://www.iterativo.do) <info@iterativo.do>

from odoo import models, api, _

class TransferPaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    @api.model
    def _create_missing_journal_for_acquirers(self, company=None):

        company = company or self.env.company
        acquirers = self.env['payment.acquirer'].search([
            ('module_state', 'in', ('to install', 'installed')),
            ('journal_id', '=', False),
            ('company_id', '=', company.id),
        ])
        Journal = journals = self.env['account.journal']
        #Remove bank acquirer Journal
        # for acquirer in acquirers.filtered(lambda l: not l.journal_id and l.company_id.chart_template_id):
        #     try:
        #         with self.env.cr.savepoint():
        #             journal = Journal.create(acquirer._prepare_account_journal_vals())
        #     except psycopg2.IntegrityError as e:
        #         if e.pgcode == psycopg2.errorcodes.UNIQUE_VIOLATION:
        #             journal = Journal.search(acquirer._get_acquirer_journal_domain(), limit=1)
        #         else:
        #             raise
        #     acquirer.journal_id = journal
        #     journals += journal

        return journals

class AccountChartTemplate(models.Model):
    _inherit = "account.chart.template"

    @api.model
    def _get_default_bank_journals_data(self):
        #Remove Bank and Cash Journal
        return []