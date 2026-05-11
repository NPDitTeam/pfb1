{
    "name": "NPD HR Withholding Tax Certificate",
    "version": "14.0.1.0.0",
    "author": "NPD",
    "license": "AGPL-3",
    "category": "Human Resources",
    "summary": "Withholding Tax Certificate for HR Payroll",
    "depends": ["employee_salary", "mail"],
    "data": [
        "data/sequence.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizard/generate_hr_wt_cert.xml",
        "wizard/send_hr_wt_cert_email.xml",
        "views/hr_withholding_tax_cert_view.xml",
    ],
    "installable": True,
    "application": False,
}
