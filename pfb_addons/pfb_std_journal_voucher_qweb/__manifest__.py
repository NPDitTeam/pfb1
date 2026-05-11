{
    'name': 'PFB Standard : Journal Standard Voucher Form Qweb',
    'version': '14.0.2',
    "author": "Perfect Blending",
    "website": "https://www.perfectblending.com",
    'category': 'Report',
    'depends': ['base',
                'web',
                ],
    'data': [
        'security/ir.model.access.csv',
        'data/paper_format.xml',
        'reports/payment_voucher.xml',
        'data/report_data.xml',
    ],
    'installable': True,
}
