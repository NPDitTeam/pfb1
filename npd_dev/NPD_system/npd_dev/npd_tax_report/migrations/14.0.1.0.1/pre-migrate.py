# -*- coding: utf-8 -*-
# Clean up leftover records from the old wizard-based design so the module
# can be upgraded to the in-report-filter design without KeyError on the
# removed model npd.tax.report.wizard.
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # 1) Remove the orphaned wizard act_window action (and its ir_model_data).
    cr.execute(
        "DELETE FROM ir_act_window WHERE res_model = 'npd.tax.report.wizard'"
    )

    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'npd_tax_report'
          AND name IN ('action_tax_report',
                       'tax_report_wizard_form',
                       'access_npd_tax_report_wizard')
        """
    )

    # 2) Drop leftover access rules and the model itself for the wizard.
    cr.execute(
        """
        DELETE FROM ir_model_access
        WHERE model_id IN (
            SELECT id FROM ir_model WHERE model = 'npd.tax.report.wizard'
        )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_fields
        WHERE model_id IN (
            SELECT id FROM ir_model WHERE model = 'npd.tax.report.wizard'
        )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE model = 'ir.model'
          AND res_id IN (
              SELECT id FROM ir_model WHERE model = 'npd.tax.report.wizard'
          )
        """
    )
    cr.execute(
        "DELETE FROM ir_model WHERE model = 'npd.tax.report.wizard'"
    )

    _logger.info("npd_tax_report: cleaned up leftover wizard records")
