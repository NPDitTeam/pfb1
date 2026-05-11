# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "Base Whatsapp Integrations",
    "author": "Softhealer Technologies",
    "license": "OPL-1",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Extra Tools",
    "summary": "Whatsapp Integration App, Sale Whatsapp Integration, Purchase Whatsapp, CRM Whatsup, Invoice Whatsapp Integration, Inventory Whatsapp Integration Odoo",
    "description": """Using this module you can direct to Clients/Vendor's WhatsApp.""",
    "version": "14.0.8",
    "depends": ['base_setup', 'mail'],
    "application": True,
    "data": [
            "security/whatsapp_security.xml",
            "security/ir.model.access.csv",
            "views/res_users_inherit_view.xml",
            "wizard/send_whasapp_number_view.xml",
            "wizard/send_whatsapp_message_view.xml",
            "views/res_partner_views.xml",
            "views/mail_message.xml",

    ],
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "price": 1,
    "currency": "EUR"
}
