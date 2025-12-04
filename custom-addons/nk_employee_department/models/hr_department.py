from odoo import models, api

class HrDepartment(models.Model):
    _inherit = 'hr.department'

    def unlink(self):
        for department in self:
            histories = self.env['nk.department.history'].search([
                ('department_id', '=', department.id)
            ])
            
            if histories:
                histories.write({
                    'department_name': department.name,
                    'department_id': False
                })
        
        return super(HrDepartment, self).unlink()