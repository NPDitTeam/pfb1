# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

import werkzeug
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import Home
from datetime import datetime


class srHome(Home):
    @http.route()
    def web_login(self, redirect=None, **kw):
        login = kw.get("login")
        password = kw.get("password")
        res_user = (
            request.env["res.users"]
            .sudo()
            .search([("login", "=", login), ("password", "=", password)])
        )
        if not res_user.user_time_validity:
            return super(srHome, self).web_login(redirect=redirect, **kw)

        current_date = datetime.now().date()
        start_date = res_user.start_date
        end_date = res_user.end_date
        if not (start_date < current_date and current_date > end_date):
            return super(srHome, self).web_login(redirect=redirect, **kw)
        else:
            return werkzeug.utils.redirect("/web/login?error=%s" % (res_user.message))
