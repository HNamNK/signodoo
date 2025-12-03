from odoo import fields, models, api
from odoo.exceptions import ValidationError

class DepartmentCode(models.Model):
    _name = 'hr.department.code'
    _description = 'Mã phòng ban'
    _order = 'name'
    
    name = fields.Char(string='Tên phòng ban', required=True)
    department_code = fields.Char(string='Mã phòng ban', required=True)
    company_id = fields.Many2one(
        'res.company', 
        string='Công ty',
    )
    
    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if record.name:
                existing = self.search([
                    ('name', '=', record.name),
                    ('id', '!=', record.id),
                ], limit=1)
                if existing:
                    raise ValidationError(f"Tên phòng ban '{record.name}' đã tồn tại!")
    
    @api.constrains('department_code')
    def _check_department_code_unique(self):
        for record in self:
            if record.department_code:
                existing = self.search([
                    ('department_code', '=', record.department_code),
                    ('id', '!=', record.id),
                ], limit=1)
                if existing:
                    raise ValidationError(f"Mã phòng ban '{record.department_code}' đã tồn tại!")
    
    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'company_id' in fields_list and 'company_id' not in defaults:
            defaults['company_id'] = self.env.company.id
        return defaults
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        
        try:
            if hasattr(self.env['ir.ui.view'], 'create_department_views'):
                self.env['ir.ui.view'].create_department_views()
        except Exception:
            pass
        
        return records

    def write(self, vals):
        old_codes = {rec.id: rec.department_code for rec in self}
        result = super().write(vals)
        
        if 'department_code' in vals:
            try:
                if hasattr(self.env['ir.ui.view'], 'create_department_views'):
                    self.env['ir.ui.view'].create_department_views()
                    
                for record in self:
                    if old_codes[record.id] != record.department_code:
                        departments = self.env['hr.department'].search([
                            ('department_code_partner_id', '=', record.id)
                        ])
                        if departments and hasattr(departments, '_compute_form_template'):
                            departments._compute_form_template()
            except Exception:
                pass
        
        return result
    
    def unlink(self):
        import re
        
        for record in self:
            if record.department_code:
                template_id = re.sub(r'[^a-zA-Z0-9]', '_', record.department_code.lower())
                view_id = f'view_nk_payment_request_form_{template_id}'
                
                try:
                    ir_model_data = self.env['ir.model.data'].search([
                        ('module', '=', 'nk_payment_request'),
                        ('name', '=', view_id)
                    ])
                    
                    if ir_model_data:
                        view = self.env['ir.ui.view'].browse(ir_model_data.res_id)
                        if view.exists():
                            view.unlink()                        
                        ir_model_data.unlink()
                except Exception:
                    pass
        
        return super().unlink()