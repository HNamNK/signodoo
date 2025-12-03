from odoo import fields, models, api
from odoo.exceptions import ValidationError 


class HrDepartment(models.Model):
    _inherit = 'hr.department'
    
    department_code_partner_id = fields.Many2one(
        'hr.department.code',
        string="Mã bộ phận",
        help="Chọn mã viết tắt của phòng ban",
    )
        
    sequence_prefix = fields.Char(
        string="Mã viết tắt", 
        help="Mã viết tắt của phòng ban",
        compute='_compute_sequence_prefix',
        store=True,
        readonly=True
    )

    form_template = fields.Char(
        string="Mã mẫu",
        help="Mã định danh mẫu cho biểu mẫu yêu cầu thanh toán tùy chỉnh",
        readonly=True,
        compute='_compute_form_template',
        store=True
    )
    
    @api.constrains('name', 'company_id')
    def _check_duplicate_department(self):
        for rec in self:
            if not rec.name or not rec.company_id:
                continue
            
            domain = [
                ('name', 'ilike', rec.name),
                ('company_id', '=', rec.company_id.id),
                ('id', '!=', rec.id)
            ]

            if self.search_count(domain):
                raise ValidationError(
                    "Tên phòng ban '%s' đã tồn tại trong công ty %s!"
                    % (rec.name, rec.company_id.name)
                )

    @api.depends('department_code_partner_id.department_code') 
    def _compute_sequence_prefix(self):
        for record in self:
            record.sequence_prefix = record.department_code_partner_id.department_code or 'Default'

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            self.department_code_partner_id = False
        return {
            'domain': {
                'department_code_partner_id': [
                    '|', 
                    ('company_id', '=', False), 
                    ('company_id', '=', self.company_id.id if self.company_id else False)
                ]
            }
        }

    @api.depends('sequence_prefix')
    def _compute_form_template(self):
        for record in self:
            record.form_template = record.sequence_prefix.lower() if record.sequence_prefix else 'default'