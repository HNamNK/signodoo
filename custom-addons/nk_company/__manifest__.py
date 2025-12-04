{
    'name': 'NK Company',
    'version': '1.0',
    'depends': ['base'],
    'summary': 'Mở rộng thông tin công ty',
    'description': """
        Module mở rộng chức năng quản lý công ty:
        - Thêm các trường thông tin: Loại hình công ty, Ngành nghề, Loại lao động.
        - Hiển thị trong form tạo và chỉnh sửa công ty.
    """,
    'author': "Nhan Kiet",
    'data': [
        'views/res_company_views.xml',
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'nk_company/static/src/css/company_dropdown.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
