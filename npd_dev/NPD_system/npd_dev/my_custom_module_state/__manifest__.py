{
    'name': "My Custom Sale Module State",
    'version': '14.0.1.0.0',
    'summary': 'Custom functions and automated actions for Sale Orders.',
    'description': """
        This module contains custom functions and automated actions
        to extend the functionality of the Sale module.
    """,
    'author': "Your Name",
    'website': "http://www.yourwebsite.com",
    'category': 'Sales',
    'depends': ['sale','pfb_npd_add_date_quatation_order'],  # This is crucial! It depends on the 'sale' module.
    'data': [
        # Add security, views, etc. here if needed.
        # 'views/my_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}