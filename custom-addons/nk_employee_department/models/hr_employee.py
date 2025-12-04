from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    department_history_ids = fields.One2many(
        'nk.department.history',
        'employee_id', 
        string='Lịch sử phòng ban',
        help='Lịch sử điều chuyển phòng ban của nhân viên'
    )
    department_history_count = fields.Integer(
        string='Số lần chuyển phòng ban',
        compute='_compute_department_history_count'
    )

    @api.depends('department_history_ids')
    def _compute_department_history_count(self):
        for employee in self:
            employee.department_history_count = len(employee.department_history_ids)

    def _get_joining_date(self):
        self.ensure_one()
        if hasattr(self, 'joining_date') and self.joining_date:
            return self.joining_date
        return fields.Date.today()
    
    @api.model_create_multi
    def create(self, vals_list):
        employees = super(HrEmployee, self).create(vals_list)
        for employee in employees:
            if employee.department_id:
                self.env['nk.department.history'].create({
                    'employee_id': employee.id,
                    'department_id': employee.department_id.id,
                    'department_name': employee.department_id.name,
                    'date_start': employee._get_joining_date(),
                    'notes': 'Phòng ban ban đầu khi vào làm'
                })
        return employees

    def write(self, vals):
        old_data = {}
        for employee in self:
            old_data[employee.id] = {
                'department': employee.department_id,
                'joining_date': employee.joining_date if hasattr(employee, 'joining_date') else None,
            }
        
        result = super(HrEmployee, self).write(vals)
        
        transfer_date = fields.Date.today()
        
        for employee in self:
            old_info = old_data.get(employee.id, {})

            if 'joining_date' in vals:
                first_history = self.env['nk.department.history'].search([
                    ('employee_id', '=', employee.id),
                ], order='date_start asc', limit=1)
                
                if first_history:
                    first_history.write({'date_start': vals['joining_date']})
            
            if 'department_id' in vals:
                old_dept = old_info.get('department')
                new_dept = employee.department_id
                
                if not new_dept or (old_dept and new_dept and old_dept.id == new_dept.id):
                    continue
                
                existing_history = self.env['nk.department.history'].search([
                    ('employee_id', '=', employee.id),
                ], limit=1)
                
                if old_dept and new_dept and old_dept.id != new_dept.id:
                    
                    if not existing_history:
                        self.env['nk.department.history'].create({
                            'employee_id': employee.id,
                            'department_id': old_dept.id,
                            'department_name': old_dept.name,
                            'date_start': employee._get_joining_date(),
                            'date_end': transfer_date,
                            'notes': 'Phòng ban ban đầu khi vào làm'
                        })
                    else:
                        current_history = self.env['nk.department.history'].search([
                            ('employee_id', '=', employee.id),
                            ('department_id', '=', old_dept.id),
                            ('date_end', '=', False)
                        ], limit=1)
                        
                        if current_history:
                            current_history.write({'date_end': transfer_date})
                    
                    self.env['nk.department.history'].create({
                        'employee_id': employee.id,
                        'department_id': new_dept.id,
                        'department_name': new_dept.name,
                        'date_start': transfer_date,
                        'notes': f'Chuyển từ phòng {old_dept.name}'
                    })
                
                elif not old_dept and new_dept:
                    existing_dept_history = self.env['nk.department.history'].search([
                        ('employee_id', '=', employee.id),
                        ('department_id', '=', new_dept.id),
                    ], limit=1)
                    
                    if not existing_dept_history:
                        if not existing_history:
                            new_date_start = employee._get_joining_date()
                            notes = 'Phòng ban ban đầu khi vào làm'
                        else:
                            new_date_start = transfer_date
                            notes = 'Gán phòng ban mới'
                        
                        self.env['nk.department.history'].create({
                            'employee_id': employee.id,
                            'department_id': new_dept.id,
                            'department_name': new_dept.name,
                            'date_start': new_date_start,
                            'notes': notes
                        })
        
        return result