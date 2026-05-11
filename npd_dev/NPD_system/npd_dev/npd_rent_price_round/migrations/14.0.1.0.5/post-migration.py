import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info(
        "[npd_rent_price_round] migrating to 14.0.1.0.5: "
        "sync use_new_calc on line tables (fix previous SQL update bypass)"
    )

    # Sync sale_order_line.use_new_calc กับ sale_order.use_new_calc
    cr.execute("""
        UPDATE sale_order_line sol
        SET use_new_calc = so.use_new_calc
        FROM sale_order so
        WHERE sol.order_id = so.id
        AND sol.use_new_calc IS DISTINCT FROM so.use_new_calc
    """)
    sol_count = cr.rowcount

    # Sync account_move_line.use_new_calc กับ account_move.use_new_calc
    cr.execute("""
        UPDATE account_move_line aml
        SET use_new_calc = am.use_new_calc
        FROM account_move am
        WHERE aml.move_id = am.id
        AND aml.use_new_calc IS DISTINCT FROM am.use_new_calc
    """)
    aml_count = cr.rowcount

    _logger.info(
        "[npd_rent_price_round] synced %s sale.order.line, %s account.move.line",
        sol_count, aml_count,
    )
