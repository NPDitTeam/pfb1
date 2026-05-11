# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "All In One PMS | Project Management System | All-in-One PMS system",

    'author': 'Softhealer Technologies',

    'website': 'https://www.softhealer.com',

    "support": "support@softhealer.com",

    'version': '14.0.15 ',

    "license": "OPL-1",

    'category': "Project",

    'summary': "Update Project Stage,Overdue Task Email,Project Checklist,Project Priority,Task Priority,Auto Project Task Stage,Task To Multiple User,Print Project Report,Task Auto Assign,Task Checklist,Task Custom Field,Update Task,Task Subtask,Task Timer odoo,Project Team Management",

    'description': """Are you still managing all projects and tasks with separate modules? That’s really a waste of time and effort. Our module, all-in-one project management system (PMS) focused on managing every aspect of your projects. You can handle projects, tasks, due dates, checklists etc in one module. All in one PMS makes it easier to manage all projects and tasks. So go ahead and download the module to improve your project management skills!""",
    'depends': [
        'base_setup', 'project', 'mail', 'hr_timesheet',
        'analytic', 'sh_message',
    ],
    "data": [
        'sh_overdue_task_email_notification/data/over_due_task_notification.xml',
        'sh_overdue_task_email_notification/data/overdue_task_email_notification_template.xml',
        'sh_task_send_email/data/task_mail_attachment.xml',
        "sh_task_custom_fields/data/task_custom_field_group.xml",
        'sh_task_cl/security/ir.model.access.csv',
        'sh_task_cl/security/task_cl_security.xml',
        'sh_overdue_task_email_notification/security/ir.model.access.csv',
        "sh_task_custom_fields/security/ir.model.access.csv",
        'sh_task_mass_update/security/ir.model.access.csv',
        'sh_task_time_adv/security/ir.model.access.csv',
        'sh_project_stages/security/ir.model.access.csv',
        'sh_project_stages/security/sh_project_stages.xml',
        'sh_project_custom_checklist/security/ir.model.access.csv',
        'sh_project_custom_checklist/security/project_cust_cl_security.xml',
        'sh_task_custom_checklist/security/ir.model.access.csv',
        'sh_task_custom_checklist/security/sh_task_custom_checklists_rights.xml',

        "sh_task_cl/wizard/import_task_wizard.xml",

        'sh_task_cl/views/task_cl.xml',
        'sh_task_cl/views/res_config_setting.xml',
        'sh_overdue_task_email_notification/views/project_task_overdue.xml',
        'sh_overdue_task_email_notification/views/project_task_overdue_config_setting.xml',
        'sh_task_send_email/views/project_task.xml',
        'sh_task_send_email/views/res_config_setting.xml',
        "sh_task_custom_fields/views/task.xml",
        "sh_task_custom_fields/views/task_tab.xml",
        "sh_task_subtasks/views/sh_stages_view.xml",
        "sh_task_subtasks/views/sh_task_view.xml",
        'sh_task_mass_update/views/mass_tag_update_action.xml',
        'sh_task_mass_update/views/mass_tag_update_wizard_view.xml',

        "sh_task_custom_checklist/wizard/import_task_wizard.xml",

        'sh_task_custom_checklist/views/task_checklist.xml',
        'sh_task_custom_checklist/views/task_checklist_template_view.xml',
        "sh_project_task_multi_users/views/project_task.xml",
        'sh_task_time_adv/views/timesheet_entry.xml',
        'sh_task_time_adv/views/templates.xml',
        'sh_task_time_adv/views/project_task_time.xml',
        'sh_task_auto_asssign_stage/views/project_task_type_view.xml',
        'sh_project_stages/views/sh_project_view.xml',
        'sh_project_stages/views/mass_project_update_action.xml',
        'sh_project_stages/views/mass_project_update_wizard_view.xml',
        'sh_project_stages/views/sh_project_stage_template.xml',
        'sh_mass_project_stage/security/ir.model.access.csv',
        'sh_mass_project_stage/views/mass_stage_update_action.xml',
        'sh_mass_project_stage/views/mass_stage_update_wizard_view.xml',
        'sh_mass_project_stage/views/res_config_setting.xml',
        'sh_project_priority/views/project_task_priority.xml',
        'sh_project_priority/views/project_project_priority.xml',
        'sh_project_priority/views/res_config_setting.xml',
        "sh_project_task_print/report/project_task_report.xml",
        "sh_project_task_print/report/project_report.xml",

        'sh_project_custom_checklist/wizard/import_project_wizard.xml',

        'sh_project_custom_checklist/views/project_checklist.xml',
        'sh_project_custom_checklist/views/project_checklist_template.xml',

        'sh_project_document/security/project_document_security.xml',
        'sh_project_document/data/project_document_email_notification_template.xml',
        'sh_project_document/data/project_document_scheduler.xml',
        'sh_project_document/views/sh_ir_attachments_views.xml',
        'sh_project_document/views/project.xml',
        'sh_project_document/views/general_config_settings.xml',

        'sh_task_document/security/task_document_security.xml',
        'sh_task_document/data/task_document_email_notification_template.xml',
        'sh_task_document/data/task_document_scheduler.xml',
        'sh_task_document/views/sh_ir_attachments_views.xml',
        'sh_task_document/views/task.xml',
        'sh_task_document/views/general_config_settings.xml',

        "views/sh_task_quick_views.xml",

        "sh_project_category/security/ir.model.access.csv",
        "sh_project_category/security/security_groups.xml",
        "sh_project_category/views/project_category.xml",
        "sh_project_category/views/res_config_setting.xml",

        'sh_project_milestone/data/project_security_group.xml',
        'sh_project_milestone/security/project_milestone_security.xml',
        'sh_project_milestone/security/ir.model.access.csv',
        'sh_project_milestone/views/project_milestone.xml',
        'sh_project_milestone/views/project_task.xml',
        'sh_project_milestone/views/project_project.xml',
        'sh_project_milestone/views/project_report.xml',

        'sh_project_team/security/ir.model.access.csv',
        'sh_project_team/security/project_team_security.xml',
        'sh_project_team/views/sh_project_team.xml',


        'sh_custom_project_template/security/project_template_security.xml',
        'sh_custom_project_template/security/ir.model.access.csv',
        'sh_custom_project_template/views/res_config_settings_views.xml',
        'sh_custom_project_template/views/project_template_views.xml',
        'sh_custom_project_template/views/project_template_task_views.xml',
        'sh_custom_project_template/views/project_project_views.xml',

    ],
    "qweb": [
        'static/src/xml/time_track.xml',
    ],
    'demo': [],
    'installable':
    True,
    'application':
    True,
    'auto_install':
    False,
    'images': ['static/description/background.gif', ],
    "price": 150,
    "currency": "EUR"
}
