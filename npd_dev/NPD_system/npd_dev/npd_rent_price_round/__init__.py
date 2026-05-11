from . import models
from . import wizard


def _post_init_hook(cr, registry):
    cr.execute("UPDATE sale_order SET use_new_calc = FALSE")
    cr.execute("UPDATE account_move SET use_new_calc = FALSE")
    # Sync line tables (related field store=True ไม่ recompute เมื่อ SQL update parent)
    cr.execute("""
        UPDATE sale_order_line sol
        SET use_new_calc = so.use_new_calc
        FROM sale_order so
        WHERE sol.order_id = so.id
    """)
    cr.execute("""
        UPDATE account_move_line aml
        SET use_new_calc = am.use_new_calc
        FROM account_move am
        WHERE aml.move_id = am.id
    """)
