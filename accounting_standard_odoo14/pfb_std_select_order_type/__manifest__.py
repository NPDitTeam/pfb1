# Copyright 2019 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

{
    'name': 'Select the order type',
    'version': '14.0.0.0.1',
    'author': 'PP',
    'license': 'AGPL-3',
    'website': '',
    'category': 'Fields',
    'depends': ['base',
                'web',
                'purchase',
                'purchase_isolated_rfq',
                ],
    'data': [
        "data/ir_sequence_data.xml",
        'views/purchase.xml',
    ],
    'installable': True,
}
