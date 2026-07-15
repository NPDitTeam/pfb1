# -*- coding: utf-8 -*-
# Clean up records from the previous client-action / wizard designs so the
# module can be upgraded to the native SQL-view report without orphan errors.
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # 1) Old client action + report (pdf/xlsx) actions defined by this module.
    cr.execute(
        """
        DELETE FROM ir_act_client
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'npd_tax_report' AND model = 'ir.actions.client'
        )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_act_report_xml
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'npd_tax_report' AND model = 'ir.actions.report'
        )
        """
    )

    # 2) Old QWeb templates / paperformat rows for this module.
    cr.execute(
        """
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'npd_tax_report' AND model = 'ir.ui.view'
        )
        """
    )

    # 3) Drop ir_model_data pointers for everything removed above so Odoo does
    #    not try to reload/relink them.
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'npd_tax_report'
          AND model IN ('ir.actions.client', 'ir.actions.report',
                        'ir.ui.view', 'report.paperformat')
        """
    )

    # 4) Remove the old transient models (they will be re-reflected as needed).
    for model_name in (
        "report.npd.tax.report",
        "npd.tax.report.view",
        "report.npd_tax_report.report_tax_report_xlsx",
        "npd.tax.report.wizard",
    ):
        cr.execute(
            """
            DELETE FROM ir_model_access
            WHERE model_id IN (SELECT id FROM ir_model WHERE model = %s)
            """,
            (model_name,),
        )
        cr.execute(
            """
            DELETE FROM ir_model_fields
            WHERE model_id IN (SELECT id FROM ir_model WHERE model = %s)
            """,
            (model_name,),
        )
        cr.execute(
            """
            DELETE FROM ir_model_data
            WHERE model = 'ir.model'
              AND res_id IN (SELECT id FROM ir_model WHERE model = %s)
            """,
            (model_name,),
        )
        cr.execute("DELETE FROM ir_model WHERE model = %s", (model_name,))

    _logger.info("npd_tax_report: cleaned up old client-action/wizard records")
