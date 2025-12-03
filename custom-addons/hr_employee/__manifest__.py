{
    'name': 'NK Employee',
    'version': '1.0',
    'depends': ['hr'],
    'summary': 'Quản lý nhân viên',
    'description': """
        Module quản lý nhân viên, gồm các thông tin nhân viên, tài khoản ngân hàng và ghi chú nội bộ.
    """,
    'author': "Nhan Kiet",
    'data': [
        'data/res_partner_data.xml',
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/hr_department_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_employee/static/src/css/hide_delete_btn.css',
        ],
    },
    'installable': True,
    'auto_install': False,
}
