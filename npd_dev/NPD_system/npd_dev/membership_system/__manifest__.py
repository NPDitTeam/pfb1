{
    'name': 'Membership System',
    'version': '1.0',
    'summary': 'Fetch and store member data from an external API',
    'description': 'This module fetches member data from an external API and stores it in a custom model.',
    'author': 'Your Name',
    'category': 'Custom',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/member_views.xml',
        'views/promotion_views.xml',
        'views/payment_confirmation_views.xml',
        'views/score_dashboard_views.xml',
        'views/activity_report_views.xml',
        'views/reward_redemption_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'membership_system/static/src/js/auto_fetch_member_data.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
