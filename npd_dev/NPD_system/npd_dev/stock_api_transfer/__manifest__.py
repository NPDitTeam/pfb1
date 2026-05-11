{
    "name": "Stock API Transfer",
    "version": "14.0.1.0.0",
    "category": "Inventory",
    "summary": "Cut stock and transfer stock via API with interface",
    "depends": ["stock", "base"],
    "data": [
        "security/stock_transfer_security.xml",
        "security/ir.model.access.csv",
        'data/ir_sequence_data.xml',
        "views/stock_transfer_menu.xml",
        "views/stock_transfer_form.xml",
        "views/res_users_view.xml",
        "wizard/stock_transfer_approval_wizard_view.xml",
    ],
    "installable": True,
    "application": True
}
