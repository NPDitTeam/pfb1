import odoo
from odoo import api, models,fields
import json
import logging
import os

from odoo import api, exceptions, models, tools,fields
from odoo.modules.module import get_module_path
_logger = logging.getLogger(__name__)


def ensure_module_state(env, modules, state):
    # read module states, bypassing any Odoo cache
    if not modules:
        return
    env.cr.execute(
        "SELECT name FROM ir_module_module " "WHERE id IN %s AND state != %s",
        (tuple(modules.ids), state),
    )
    names = [r[0] for r in env.cr.fetchall()]
    if names:
        raise FailedUpgradeError(
            "The following modules should be in state '%s' "
            "at this stage: %s. Bailing out for safety."
            % (
                state,
                ",".join(names),
            ),
        )
    
class Module(models.Model):
    _inherit = 'ir.module.module'

    skip_update = fields.Boolean('Skip Auto Update')

    @api.model
    def skip_update_auto(self):
        mods = self.search([("skip_update","=",True)])
        for rec in mods:
            rec.write({'skip_update':False})

class BaseModuleUpgrade(models.TransientModel):
    _inherit = "base.module.upgrade"
    _description = "Upgrade Module"
    
    def upgrade_module(self):
        Module = self.env['ir.module.module']

        # install/upgrade: double-check preconditions
        mods = Module.search([('state', 'in', ['to upgrade', 'to install']),("skip_update","=",False)])
        mods_skip = Module.search([("skip_update","=",True)])
        if mods:
            query = """ SELECT d.name
                        FROM ir_module_module m
                        JOIN ir_module_module_dependency d ON (m.id = d.module_id)
                        LEFT JOIN ir_module_module m2 ON (d.name = m2.name)
                        WHERE m.id in %s  and (m2.state IS NULL or m2.state IN %s) """
            if mods_skip:
                query += " and d.module_id not in %s "
                self._cr.execute(query, (tuple(mods.ids), ('uninstalled',),(tuple(mods_skip.ids))))
                for module in mods_skip:
                    module.write({'state':'installed'})
            else:
                self._cr.execute(query, (tuple(mods.ids), ('uninstalled',)))
            unmet_packages = [row[0] for row in self._cr.fetchall()]
            if unmet_packages:
                raise UserError(_('The following modules are not installed or unknown: %s') % ('\n\n' + '\n'.join(unmet_packages)))

            mods.download()

        # terminate transaction before re-creating cursor below
        self._cr.commit()
        api.Environment.reset()
        odoo.modules.registry.Registry.new(self._cr.dbname, update_module=True)

        return {'type': 'ir.actions.act_window_close'}