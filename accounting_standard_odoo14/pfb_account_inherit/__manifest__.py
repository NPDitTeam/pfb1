# -*- coding: utf-8 -*-
{
    'name': "PFB Standard : Account Inherit",
    'summary': "pfb_account_inherit",
    'description': "pfb_account_inherit",
    "author": "Perfect Blending",
    "website": "https://www.perfectblending.com",
    'category': 'Uncategorized',
    'version': '14.0.1',
    'depends': ['base',
                'account',
                'account_cheque',
                'account_billing',
                'account_voucher'
                ],
    'data': [
        'views/view_inherit_customer.xml',
        'views/view_inherit_vendor.xml',
    ],

}
