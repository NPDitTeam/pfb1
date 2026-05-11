{
    'name': "Meeting Room Management",
    'name_vi_VN': "Quản lý phòng họp",

    'summary': """
Manage and allow booking meeting rooms
    """,
    'summary_vi_VN': """
Quản lý và cho phép đặt phòng họp
    """,

    'description': """
Key features
============
* Manage meeting rooms
* Allow booking meeting rooms

Supported Editions
==================
1. Community Edition
2. Enterprise Edition

    """,

    'description_vi_VN': """
Tính năng nổi bật
=================
* Quản lý phòng họp
* Cho phép đặt phòng họp

Ấn bản được hỗ trợ
==================
1. Ấn bản Community
2. Ấn bản Enterprise

    """,

    'author': "Viindoo",
    'website': "https://viindoo.com/apps/app/14.0/viin_meeting_room",
    'live_test_url': "https://v14demo-int.viindoo.com",
    'live_test_url_vi_VN': "https://v14demo-vn.viindoo.com",
    'support': "apps.support@viindoo.com",
    'category': 'Administration',
    'version': '0.1.0',

    # any module necessary for this one to work correctly
    'depends': ['calendar', 'to_base','hr'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/root_menu.xml',
        'views/calendar_meeting_room_views.xml',
        'views/calendar_event_views.xml',
        'views/calender_templates.xml',
    ],
    'qweb': [
        "static/src/xml/web_calendar.xml",
    ],
    'images' : [
        'static/description/main_screenshot.png'
    ],
    'post_init_hook':'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'price': 45,
    'currency': 'EUR',
    'license': 'OPL-1',
}
