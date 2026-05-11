# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.
{
    "name": "All In One HRMS - Community Edition | Human Resource Management System | Friendly HRMS System | HR Management System | HRMS Dashboard",

    'author': 'Softhealer Technologies',

    'website': 'https://www.softhealer.com',

    "support": "support@softhealer.com",

    'version': '14.0.11',

    "license": "OPL-1",

    'category': "Human Resources",

    'summary': "Employee Promotion,Employee Overtime,Employee Medical,Attendance Chatter,Employee Leave,Employee Expense,Employee Idea,Employee Checklist,Employee Complain,Update Employee,Employee Document,Employee Extra Fields,Visa,Passport,Dashboard odoo",

    'description': """In any organization, the most significant task is that managing their human capital. We have developed an All-in-1 HRMS module for efficient management of the human resource in an organization. Our HRMS module helps to manage HR-related activities easily and efficiently. So get the best HRMS at a low cost!""",

    "depends": ['hr_holidays', 'mail', 'web', 'bus', 'hr_attendance', 'hr_contract', 'hr_expense', 'hr_recruitment', 'sh_hr_payroll', 'sh_hr_payroll_account', 'sh_base_whatsapp_integration', 'sh_message'],

    "data": [


        'sh_leave_notification/security/ir.model.access.csv',
        'sh_leave_notification/security/leave_notification_security.xml',
        'sh_leave_notification/data/hr_holidays_leave_email_template.xml',
        'sh_leave_notification/data/leave_notification_schedular.xml',
        'sh_leave_notification/views/res_config_settings.xml',
        'sh_leave_notification/views/sh_leave.xml',


        'hr_employee_medical/security/ir.model.access.csv',
        'hr_employee_medical/security/emp_medical_security.xml',
        'hr_employee_medical/data/expired_medical_email_template.xml',
        'hr_employee_medical/data/notify_medical_cron.xml',
        'hr_employee_medical/views/res_company_view.xml',
        'hr_employee_medical/views/sh_employee_view.xml',
        'hr_employee_medical/views/res_config_setting_view.xml',
        'hr_employee_medical/views/medical_type_view.xml',
        'hr_employee_medical/views/employee_medical_information.xml',


        'sh_hr_dashboard/security/ir.model.access.csv',
        'sh_hr_dashboard/security/hr_dashboard_security.xml',
        'sh_hr_dashboard/data/dashboard_data.xml',
        'sh_hr_dashboard/views/templates.xml',
        'sh_hr_dashboard/views/annoucement_view.xml',
        'sh_hr_dashboard/views/hr_dashboard.xml',


        'sh_hr_overtime/security/ir.model.access.csv',
        'sh_hr_overtime/security/sh_overtime_security.xml',
        'sh_hr_overtime/data/sh_overtime_sequence.xml',
        'sh_hr_overtime/data/new_overtime_mail.xml',
        'sh_hr_overtime/views/sh_hr_overtime.xml',
        'sh_hr_overtime/wizard/sh_ot_reject_wizard.xml',
        'sh_hr_overtime/views/sh_ot_types.xml',


        'sh_hr_promotion/security/ir.model.access.csv',
        'sh_hr_promotion/security/sh_promotion_security.xml',
        'sh_hr_promotion/views/sh_hr_promotion.xml',
        'sh_hr_promotion/views/sh_promotion_types.xml',
        'sh_hr_promotion/reports/sh_hr_promotion_report.xml',


        'sh_hr_expense_cancel/security/hr_security.xml',
        'sh_hr_expense_cancel/data/data.xml',
        'sh_hr_expense_cancel/views/hr_config_settings.xml',
        'sh_hr_expense_cancel/views/views.xml',

        'sh_hr_attandance_chatter/views/attendance_chatter.xml',

        'sh_emp_idea/security/ir.model.access.csv',
        'sh_emp_idea/security/idea_security.xml',
        'sh_emp_idea/data/sh_idea_sequence.xml',
        'sh_emp_idea/data/new_idea_mail.xml',
        'sh_emp_idea/views/sh_idea.xml',
        'sh_emp_idea/wizard/sh_idea_approve_wizard.xml',
        'sh_emp_idea/wizard/sh_idea_refuse_wizard.xml',
        'sh_emp_idea/views/sh_idea_categories.xml',

        'sh_employee_cl/security/ir.model.access.csv',
        'sh_employee_cl/security/sh_employee_cl_security.xml',
        "sh_employee_cl/wizard/import_entry_wizard.xml",
        "sh_employee_cl/wizard/import_exit_wizard.xml",
        'sh_employee_cl/views/employee_cl.xml',

        'sh_emp_complain/security/ir.model.access.csv',
        'sh_emp_complain/security/sh_complain_security.xml',
        'sh_emp_complain/data/sh_complain_sequence.xml',
        'sh_emp_complain/data/new_complain_mail.xml',
        'sh_emp_complain/views/sh_complain.xml',
        'sh_emp_complain/wizard/sh_complain_resolve_wizard.xml',
        'sh_emp_complain/wizard/sh_complain_refuse_wizard.xml',
        'sh_emp_complain/views/sh_effect.xml',
        'sh_emp_complain/views/sh_complain_categories.xml',
        'sh_emp_complain/report/complain_report.xml',

        'sh_emp_sequence/security/emp_sequence_security.xml',
        'sh_emp_sequence/data/employee_seq_data.xml',
        'sh_emp_sequence/views/res_config_setting_view.xml',
        'sh_emp_sequence/views/hr_employee_view.xml',

        'sh_emp_mass_tags/security/ir.model.access.csv',
        'sh_emp_mass_tags/security/hr_employee_mass_tags_security.xml',
        'sh_emp_mass_tags/wizard/emp_mass_tag.xml',

        "sh_emp_mass_update/security/ir.model.access.csv",
        "sh_emp_mass_update/security/emp_mass_update_security.xml",
        "sh_emp_mass_update/views/mass_tag_update_action.xml",
        "sh_emp_mass_update/views/mass_tag_update_wizard_view.xml",

        'sh_emp_own_records/security/employee_security.xml',

        'sh_employee_document/security/employee_document_security.xml',
        'sh_employee_document/data/employee_document_email_notification_template.xml',
        'sh_employee_document/data/employee_document_scheduler.xml',
        'sh_employee_document/views/sh_ir_attachments_views.xml',
        'sh_employee_document/views/employee.xml',
        'sh_employee_document/views/general_config_settings.xml',


        'sh_employee_passport/security/ir.model.access.csv',
        'sh_employee_passport/security/emp_passport_security.xml',
        'sh_employee_passport/data/passport_data.xml',
        'sh_employee_passport/data/passport_expired_email_template.xml',
        'sh_employee_passport/data/notify_visa_cron.xml',
        'sh_employee_passport/views/res_company_view.xml',
        'sh_employee_passport/views/res_config_setting_view.xml',
        'sh_employee_passport/views/employee.xml',
        'sh_employee_passport/views/employee_passport.xml',

        'sh_employee_extra_fields/security/ir.model.access.csv',
        'sh_employee_extra_fields/security/emp_extra_fields_security.xml',
        'sh_employee_extra_fields/views/sh_company_facilities.xml',
        'sh_employee_extra_fields/views/sh_employee_religion.xml',
        'sh_employee_extra_fields/views/sh_employee_emergency.xml',
        'sh_employee_extra_fields/views/sh_employee_extra_fieds.xml',


        "sh_employee_custom_fields/data/employee_custom_field_group.xml",
        "sh_employee_custom_fields/security/ir.model.access.csv",
        "sh_employee_custom_fields/views/hr_employee.xml",
        "sh_employee_custom_fields/views/employee_tab.xml",

        'sh_employee_custom_checklist/security/ir.model.access.csv',
        'sh_employee_custom_checklist/security/emp_cust_checklist_security.xml',
        "sh_employee_custom_checklist/wizard/import_entry_wizard.xml",
        "sh_employee_custom_checklist/wizard/import_exit_wizard.xml",
        'sh_employee_custom_checklist/views/employee_checklist.xml',
        'sh_employee_custom_checklist/views/employee_checklist_entry_template.xml',
        'sh_employee_custom_checklist/views/employee_checklist_exit_template.xml',


        'sh_hr_mass_approve_leave/security/hr_employee_mass_leave_security.xml',
        'sh_hr_mass_approve_leave/data/data.xml',

        'sh_payslip_cancel/security/sh_payslip_security.xml',
        'sh_payslip_cancel/views/hr_payslip_views.xml',

        'sh_payslip_dynamic_approval/security/ir.model.access.csv',
        'sh_payslip_dynamic_approval/security/sh_payslip_dynamic_approval_security.xml',
        'sh_payslip_dynamic_approval/data/mail_data.xml',
        'sh_payslip_dynamic_approval/views/rejection_wizard.xml',
        'sh_payslip_dynamic_approval/views/payroll_approval_config.xml',
        'sh_payslip_dynamic_approval/views/payroll_approval_line.xml',
        'sh_payslip_dynamic_approval/views/inherit_hr_payslip.xml',
        'sh_payslip_dynamic_approval/views/approval_info.xml',

        "sh_payslip_dynamic_cheque/security/ir.model.access.csv",
        "sh_payslip_dynamic_cheque/security/sh_payslip_dynamic_cheque_security.xml",
        "sh_payslip_dynamic_cheque/views/sh_cheque_format_view.xml",
        "sh_payslip_dynamic_cheque/views/sh_payslip_view.xml",
        "sh_payslip_dynamic_cheque/views/sh_report_print_cheque.xml",

        'sh_payslip_send_email/security/ir.model.access.csv',
        'sh_payslip_send_email/security/sh_payslip_send_email_security.xml',
        'sh_payslip_send_email/data/template_hr_payslip_send_auto_email.xml',
        'sh_payslip_send_email/views/employee_payslip.xml',

        "sh_payslip_whatsapp_integration/security/whatsapp_security.xml",
        "sh_payslip_whatsapp_integration/views/res_config_settings.xml",
        "sh_payslip_whatsapp_integration/views/base_wp_message_view_inherit.xml",
        "sh_payslip_whatsapp_integration/views/payroll_inherit_view.xml",

        'sh_overtime_in_payslip/security/ir.model.access.csv',
        'sh_overtime_in_payslip/data/hr_payroll_data.xml',
        'sh_overtime_in_payslip/views/hr_contract_views.xml',
        'sh_overtime_in_payslip/views/overtime_config_weekday.xml',
        'sh_overtime_in_payslip/views/overtime_config_weekend.xml',
        'sh_overtime_in_payslip/views/res_config_settings_views.xml',


        'sh_leave_attachment/views/sh_leave_attachment_security.xml',
        'sh_leave_attachment/views/sh_leave_type.xml',

        'sh_payslip_batch/views/payslip_count.xml',

        "sh_auto_checkout_attendance/data/data.xml",
        "sh_auto_checkout_attendance/views/res_config_settings.xml",


        'sh_hr_policy/security/ir.model.access.csv',
        'sh_hr_policy/views/res_company_views.xml',
        'sh_hr_policy/views/hr_department_views.xml',
        'sh_hr_policy/views/hr_contract_views.xml',
        'sh_hr_policy/wizard/sh_open_company_policy_wizard_views.xml',
        'sh_hr_policy/wizard/sh_open_department_policy_wizard_views.xml',
        'sh_hr_policy/wizard/sh_open_blank_data_wizard_views.xml',

        'sh_hr_resignation/security/ir.model.access.csv',
        'sh_hr_resignation/security/sh_resignation_security.xml',
        'sh_hr_resignation/data/sh_resignation_sequence.xml',
        'sh_hr_resignation/data/sh_resignation_mail_template.xml',
        'sh_hr_resignation/wizard/sh_resignation_approve_wizard_views.xml',
        'sh_hr_resignation/wizard/sh_resignation_refuse_wizard_views.xml',
        'sh_hr_resignation/views/hr_employee_views.xml',
        'sh_hr_resignation/views/sh_resignation_views.xml',
        'sh_hr_resignation/views/sh_resignation_type_views.xml',


        'views/sh_all_in_one_hrms_config_views.xml',

    ],
    'qweb': [
        'static/src/xml/hr_dashboard.xml',
        'static/src/xml/hr_manager_dashboard.xml',
    ],

    'images': ['static/description/background.gif', ],

    "installable": True,
    "application": True,
    "autoinstall": False,
    "price": 160,
    "currency": "EUR"
}
