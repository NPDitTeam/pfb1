{
    'name': 'Partner Phone Extension002',
    'version': '1.0',
    'category': 'Contacts',
    'summary': 'Add phone extension field for res.partner',
    'description': """
        Adds a phone_extension field to res.partner and provides a button to update this field based on phone and mobile fields.
    """,
    'depends': ['base'],
    'data': [
        'views/res_partner_view.xml',
    ],

}
