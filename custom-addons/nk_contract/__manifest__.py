{
    'name': 'NK Contract',
    'version': '1.0',
    'summary': 'Add Citizen ID to HR Employee',
    'depends': ['hr','nk_salary_policies'],
    'data': [
        'security/ir.model.access.csv',
        'views/contract_view.xml',
        'views/hr_employee_contract_create_view.xml',
        'views/hr_employee_contract_regeneration_view.xml',
        'views/types.xml',
        'views/menu.xml',
    
    ],
    'assets': {
        'web.assets_backend': [
            
            'nk_contract/static/src/js/hide_menu.js',
            'nk_contract/static/src/css/duration_mont.css',
            

        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
}