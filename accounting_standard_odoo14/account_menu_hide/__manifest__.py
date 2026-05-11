{
    'name': 'PFB account menu hide',
    'version': '14.0.1',
    'description': 'account menu hide',
    'summary': 'hide menu',
    'author': 'PS',
    'website': '',
    'license': 'LGPL-3',
    'category': 'account',
    'depends': [
        'account',
        'bi_import_chart_of_accounts',
        'contract',
        'account_dynamic_reports',
        'account_payment_return',
    ],
    'data': [
        'views/account_menu_hide.xml'
    ],
   
    'auto_install': False,
    'application': False,
}