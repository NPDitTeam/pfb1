import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info("[npd_rent_price_round] migrating to 14.0.1.0.4: marking existing SO/Invoice as old calc")

    cr.execute("UPDATE sale_order SET use_new_calc = FALSE")
    so_count = cr.rowcount
    cr.execute("UPDATE account_move SET use_new_calc = FALSE")
    move_count = cr.rowcount

    # Sync line tables ด้วย เพราะ related field store=True ไม่ recompute เมื่อ SQL update
    cr.execute("""
        UPDATE sale_order_line sol
        SET use_new_calc = so.use_new_calc
        FROM sale_order so
        WHERE sol.order_id = so.id
    """)
    sol_count = cr.rowcount
    cr.execute("""
        UPDATE account_move_line aml
        SET use_new_calc = am.use_new_calc
        FROM account_move am
        WHERE aml.move_id = am.id
    """)
    aml_count = cr.rowcount

    _logger.info(
        "[npd_rent_price_round] marked %s sale.order, %s account.move, "
        "%s sale.order.line, %s account.move.line",
        so_count, move_count, sol_count, aml_count,
    )
