# __manifest__.py

{
    'name': 'NPD Custom Contact Required Fields',
    'version': '1.0',
    'summary': 'Makes VAT, Zip, and Phone fields mandatory in Contacts',
    'description': 'A module to make the VAT, Zip Code, and Phone fields required on the Contacts form.',
    'author': 'NPD',
    'depends': ['base'],
    'data': [
            'views/res_partner.xml'
    ],
    'installable': True,
    'application': False,
}
