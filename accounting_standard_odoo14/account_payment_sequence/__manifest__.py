{
    'name': 'Account Payment Sequence',
    'version': '14.0.1',
    'summary': 'Account Payment Sequence',
    'description': 'Account Payment',
    'category': 'account',
    'author': 'Phongsan Boriphan',
    'website': 'www.ashiraplus.co.th',
    "license": "AGPL-3",
    'depends': ['base','account','account_payment_invoice','account_journal_sequences'],
    'data': [
        'data/ir_sequence_data.xml',
        'views/account_payment_view.xml'
    ],
    'installable': True,
    'auto_install': False,
}