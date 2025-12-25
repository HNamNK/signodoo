from odoo import api, fields, models, _


class NkSalarypoliciesLog(models.Model):
    _name = "nk.salary.policies.log"
    _description = "Salary policies Change Log"
    _order = "create_date desc"
    
    batch_id = fields.Many2one(
        'nk.salary.policies.batch',
        string="Batch",
        required=True,
        ondelete='cascade',
        index=True,
    )
    
    policies_ids = fields.Many2one(
        'nk.salary.policies',
        string="policies Record",
        ondelete='set null',
        index=True,
    )
    
    company_id = fields.Many2one(
        'res.company',
        string="Công ty",
        required=True,
        index=True,
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        string="Nhân viên",
        index=True,
    )
    
    user_id = fields.Many2one(
        'res.users',
        string="Người thực hiện",
        default=lambda self: self.env.user,
        required=True,
    )
    
    create_date = fields.Datetime(
        string="Thời gian",
        readonly=True,
        index=True,
    )
    
    log_level = fields.Selection([
        ('batch', 'Nhật ký bảng Chính Sách'),
        ('record', 'Nhật ký từng nhân viên'),
    ], string='Cấp độ', required=True, index=True)
    
    action_type = fields.Selection([

        ('policies_state_change', 'Thay đổi trạng thái '),
        ('policies_field_change', 'Cập nhật thông tin '),
    ], string='Loại thao tác', required=True)
    
    field_name = fields.Char(string='Tên trường')
    old_value = fields.Text(string='Giá trị cũ')
    new_value = fields.Text(string='Giá trị mới')
    
    trigger_batch_id = fields.Many2one(
        'nk.salary.policies.batch',
        string="Do Bảng Chính Sách",
    )
    
    description = fields.Text(string='Chi tiết')
    
    employee_identification = fields.Char(
        related='employee_id.identification',
        string='Số CCCD',
        store=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        
        for vals in vals_list:
            if 'old_value' in vals and vals['old_value']:
                vals['old_value'] = self._clean_value(vals['old_value'])
            if 'new_value' in vals and vals['new_value']:
                vals['new_value'] = self._clean_value(vals['new_value'])
        return super().create(vals_list)
    
    def write(self, vals):
        
        if 'old_value' in vals and vals['old_value']:
            vals['old_value'] = self._clean_value(vals['old_value'])
        if 'new_value' in vals and vals['new_value']:
            vals['new_value'] = self._clean_value(vals['new_value'])
        return super().write(vals)
    
    def _clean_value(self, value):
        
        if not value:
            return value
        value = str(value)
        if value.endswith('.0'):
            return value[:-2]
        return value