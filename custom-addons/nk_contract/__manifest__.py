{
    'name': 'NK Contract',
    'version': '1.0',
    'summary': 'Add Citizen ID to HR Employee',
    'depends': ['hr'],
    'data': [
        'views',

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