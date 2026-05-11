# Copyright 2020 CorTex IT Solutions Ltd. (<https://cortexsolutions.net/>)
# License OPL-1

from odoo import models, api


class IRModuleMultiUninstall(models.TransientModel):
    _name = 'ir.module.module.multi.uninstall.wizard'

    def uninstall_multi_module(self):
        modules = self.env['ir.module.module'].browse(self._context.get('active_ids')).filtered(lambda x: x.state == 'installed')
        if modules:
            modules.button_immediate_uninstall()
