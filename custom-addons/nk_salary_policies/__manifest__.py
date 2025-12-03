{
    'name': 'NK Salary Policies',
    'version': '1.0',
    'summary': 'Add Citizen ID to HR Employee',
    'depends': ['hr', 'hr_contract', 'hr_employee','web'],
    'data': [
        'security/salary_policies_security.xml',
        'security/ir.model.access.csv',
        'views/nk_salary_policies.xml',
        'views/nk_salary_policies_field_config.xml',
        'views/nk_salary_policies_batch.xml',
        'views/nk_salary_policies_log.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            
            'nk_salary_policies/static/src/css/salary_policy_list.css',
            'nk_salary_policies/static/src/fields/null_numeric_field.js',
            'nk_salary_policies/static/src/fields/null_numeric_field.xml',
            'nk_salary_policies/static/src/fields/null_numeric_field.css',

        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
}