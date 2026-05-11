{
    'name': 'KTB Bank statment import',
    'version': '14.0.1',
    'summary': 'KTB Bank import',
    'description': 'KTB Bank import',
    'category': 'account',
    'author': 'BPV',
    'license': '',
    'depends': ['account'],
    'data': [
        'views/bank_statement.xml',
        'security/ir.model.access.csv'
    ],
    'installable': True,
    'auto_install': False,
    'external_dependencies': {
        'python': ['pandas'],
    }
}