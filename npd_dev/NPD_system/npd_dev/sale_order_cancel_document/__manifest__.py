{
    "name": "Sale Order Cancel Document With Reason & Log",
    "version": "14.0.1.0.0",
    "depends": ["sale", "stock", "account", "branch"],
    "author": "NPD Custom",
    "category": "Sales",
    "data": [
        "security/ir.model.access.csv",
        "views/cancel_document_wizard_views.xml",
        "views/cancelled_document_log_views.xml",
    ],
    "installable": True,
    "application": False,
}
