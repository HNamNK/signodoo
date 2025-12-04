{
    'name': 'NK Employee Department',
    'author': 'Nhan Kiet',
    'depends': ['hr', 'hr_skills', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}