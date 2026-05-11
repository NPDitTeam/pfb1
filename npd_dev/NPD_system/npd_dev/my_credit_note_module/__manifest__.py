# my_credit_note_module/__manifest__.py
{
    'name': 'Credit Note VAT Check',
    'version': '1.0',
    'summary': 'Ensures 7% VAT on credit note lines if original invoice is paid.',
    'description': """
        This module customizes the behavior of credit notes (refunds) in Odoo.
        It checks the original invoice referenced by 'reversed_entry_id'.
        If the original invoice is fully paid, all product lines on the credit note
        will automatically have 'Sales VAT 7%' applied as their tax.
    """,
    'category': 'Accounting',
    'author': 'Your Name/Company',
    'website': 'http://www.yourwebsite.com',
    'depends': ['account', 'account_invoice_refund_link'],
    'data': [

        'views/account_move_views.xml', # Optional, if you add any new fields/buttons

    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}