{
    'name': 'Petty Cash Balance',
    'version': '14.1.0.1',
    'description': 'Petty Cash Balance',
    'summary': 'Petty Cash Balance',
    'author': 'pfb',
    'website': 'www.pfb.co.th',
    'license': 'LGPL-3',
    'category': 'account',
    'depends': [
        'petty_cash'
    ],
    "data": [
        "data/ir_sequence_data.xml",
        "security/ir.model.access.csv",
        "views/cash_type_views.xml",
        "views/petty_cash_balance_views.xml"
    ],
    'auto_install': False,
    'application': False,
}