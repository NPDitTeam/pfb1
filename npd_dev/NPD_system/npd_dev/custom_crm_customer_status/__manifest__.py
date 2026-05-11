{
    'name': 'CRM Customer Status',
    'version': '14.0.1.0.0',
    'category': 'CRM',
    'summary': 'Add customer status field to CRM lead',
    'depends': ['crm','sale','account'],
    'data': [
        'views/crm_lead_view.xml',
        'views/crm_lead_kanban_view.xml',
        'views/crm_lead_overdue_popup_view.xml',
    ],
    'installable': True,
}
