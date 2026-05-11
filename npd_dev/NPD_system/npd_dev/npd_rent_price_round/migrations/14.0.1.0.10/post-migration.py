import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Clean up security group + category records from v14.0.1.0.9.

    v14.0.1.0.9 used res.groups + ir.module.category to control who can
    edit `use_new_calc`. v14.0.1.0.10 switches to a Boolean field on
    res.users, so those records are now orphan and may cause the user
    form to render the groups widget as a flat list. Remove them via
    ORM so all FK references (ir.rule, ir.model.access, m2m links) are
    cleaned up properly.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Both ID variants used during the v14.0.1.0.9 development iteration
    group_xmlids = [
        'npd_rent_price_round.group_use_new_calc_editor',
        'npd_rent_price_round.group_use_new_calc_editable',
    ]
    category_xmlids = [
        'npd_rent_price_round.module_category_use_new_calc_editing',
        'npd_rent_price_round.module_category_npd_rent_price_round',
    ]

    removed_groups = 0
    for xmlid in group_xmlids:
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            rec.unlink()
            removed_groups += 1

    removed_categories = 0
    for xmlid in category_xmlids:
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            rec.unlink()
            removed_categories += 1

    _logger.info(
        "[npd_rent_price_round] migrating to 14.0.1.0.10: "
        "removed %s orphan group(s), %s orphan category(s); "
        "user form should now render normally",
        removed_groups, removed_categories,
    )
