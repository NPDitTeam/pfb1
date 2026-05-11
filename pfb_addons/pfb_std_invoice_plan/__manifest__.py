# Copyright 2019 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

{
    'name': 'Invoice Plan Amount',
    'version': '14.0.0.0.1',
    'author': 'PP',
    'license': 'AGPL-3',
    'website': '',
    'category': 'Fields',
    'depends': ['base',
                'web',
                'purchase_invoice_plan',
                'purchase',
                'purchase_work_acceptance',
                'purchase_work_acceptance_invoice_plan',
                ],


    'data': [
        'views/purchase_invoice_plan.xml',
        'views/instalment.xml'

    ],
    'installable': True,
}
