{
    "name": "PFB Stock On hand by Date",
    "summary": """PFB Stock On hand by Date show qty with lot and secondary qty""",
    "version": "14.0.1",
    "license": "AGPL-3",
    "author": "perfectblending",
    'website': 'https://www.perfectblending.com/',
    "depends": ["stock","web","report_xlsx_helper","secondary_uom_inventory_app"],
    "data": [
        "security/ir.model.access.csv",
        "data/paper_format.xml",
        "data/report_data.xml",
        "reports/stock_onhand_report.xml",
        "wizard/stock_onhand_report_wizard_view.xml"
    ],
    "installable": True,
}
