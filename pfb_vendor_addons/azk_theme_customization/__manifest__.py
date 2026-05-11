{
    'name': "Odoo theme customization",
    
    'summary': """
       Odoo theme customization enables customizing and showcasing your branding images and colors in the backend.
        
        """,
        
    'description': """
        Odoo theme customization enables customizing and showcasing your branding images and colors in the backend.
    """,
    
    'author': "Azkatech SAL",
    'website': "http://www.azka.tech",
    'category': 'Website',
    'version': '14.0.0.0.1',
    "license": "AGPL-3",
    "support": "info@azka.tech",
    
    "price": 30,
    "currency": "USD",
    
    'depends': ['base', 'base_setup'],
    
    'data': [
        "security/ir.model.access.csv",
        "views/res_config.xml",
        "views/theme_views.xml",
        "data/theme_data.xml",
        "views/template.xml",
    ],
    
    'application': False,
    'images': ['static/description/banner.gif'],
}
