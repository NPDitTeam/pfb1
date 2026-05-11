{
    'name': 'User Branch Filter Setting',
    'version': '14.0.1.0.0',
    'category': 'Settings',
    'summary': 'Add user setting to bypass branch filter in account.move',
    'description': """
        This module adds a user setting that allows bypassing the branch filter
        in account.move records when the checkbox is ticked.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'account', 'branch'],
    'data': [
        'views/res_users_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}