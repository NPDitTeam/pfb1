# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

{
    "name": "User Login Validity",
    "version": "14.0.0.1",
    "category": "Extra Addons",
    "license": "OPL-1",
    'summary': 'User login Validity User login restrict User login within time period User login within time period login time validity user can login between given date user can login for particular date Restrict user login Restrict date to login',
    "description": """
        User login Validity
        User login restrict
        User login within time period
        login time validity
        user can login between given date
        user can login for particular date
        Restrict user login
        Restrict date to login
        Login custom message
        login error message
        inherit controller
        inherit res.users
        customize login fail message
        login access validity
        login access time period
        allow login between given time period
        allow login between days
        allow login for specific dates
        limited login access
        login security
        user can login for specific given date
        allow user to login for specific date
    """,
    "price": 10,
    "currency": 'EUR',
    'author': 'Sitaram',
    "url": "https://sitaramsolutions.in",
    "depends": ["web", "base"],
    "data": [
        "views/inherited_res_users.xml",
    ],
    "qweb": [],
    'installable': True,
    'auto_install': False,
    'live_test_url':'https://youtu.be/wAk_8kEr7Sc',
    "images":['static/description/banner.png'],
}
