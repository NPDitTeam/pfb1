{
    'name': 'Debit Note Approval Flow',
    'version': '14.0.1.0',
    'author': 'NPD Dev',
    'depends': [
        'account',
        'scrap_reason_code',
        'bi_sale_purchase_discount_with_tax'
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/request_approval_wizard_view.xml',
        'wizard/approval_wizard_view.xml',
        'views/account_move_view.xml',
    ],
    'installable': True,
    'application': False,
}