# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeContractWizard(models.TransientModel):
    """
    Wizard tạo/tái tạo hợp đồng hàng loạt
    KHÔNG kiểm tra policies
    """
    _name = 'hr.employee.contract.wizard'
    _description = 'Wizard Tạo/Tái Tạo Hợp Đồng Hàng Loạt'

    name = fields.Char(
        string='Tên',
        compute='_compute_name',
        store=False
    )
    
    action_type = fields.Selection([
        ('create', 'Tạo mới'),
        ('regenerate', 'Tái tạo'),
    ], string='Loại thao tác',
       required=True,
       default='create')

    employee_ids = fields.Many2many(
        'hr.employee',
        string='Nhân viên',
        required=True
    )
    
    employee_count = fields.Integer(
        string='Số lượng nhân viên',
        compute='_compute_employee_count',
        store=False
    )
    
    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for wizard in self:
            wizard.employee_count = len(wizard.employee_ids)
    
    @api.depends('action_type', 'employee_count')
    def _compute_name(self):
        for wizard in self:
            action_name = 'Tạo mới' if wizard.action_type == 'create' else 'Tái tạo'
            wizard.name = f"{action_name} hợp đồng ({wizard.employee_count} NV)"
    
    @api.onchange('employee_ids')
    def _onchange_employee_ids(self):
        """Validate nhân viên khi chọn"""
        if not self.employee_ids or not self.action_type:
            return
        
        if self.action_type == 'create':
            employees_with_contract = self.employee_ids.filtered(lambda e: e.contract_ids)
            
            if employees_with_contract:
                employee_names = employees_with_contract.mapped('name')
                return {
                    'warning': {
                        'title': _('Cảnh báo'),
                        'message': _(
                            'Các nhân viên sau ĐÃ CÓ hợp đồng:\n%s\n\n'
                            'Vui lòng bỏ chọn hoặc sử dụng "Tái tạo hợp đồng".'
                        ) % '\n'.join([f'• {name}' for name in employee_names])
                    }
                }
        
        elif self.action_type == 'regenerate':
            employees_without_contract = self.employee_ids.filtered(lambda e: not e.contract_ids)
            
            if employees_without_contract:
                employee_names = employees_without_contract.mapped('name')
                return {
                    'warning': {
                        'title': _('Cảnh báo'),
                        'message': _(
                            'Các nhân viên sau CHƯA CÓ hợp đồng:\n%s\n\n'
                            'Vui lòng bỏ chọn hoặc sử dụng "Tạo hợp đồng mới".'
                        ) % '\n'.join([f'• {name}' for name in employee_names])
                    }
                }
    
    def action_process_contracts(self):
        """Xử lý tạo/tái tạo hợp đồng"""
        self.ensure_one()
        
        if not self.employee_ids:
            raise UserError(_('Vui lòng chọn ít nhất một nhân viên.'))
        
        _logger.info(
            f"Processing {self.action_type} for {len(self.employee_ids)} employees"
        )
        
        if self.action_type == 'create':
            return self.employee_ids.create_contracts_batch()
        elif self.action_type == 'regenerate':
            return self.employee_ids.regenerate_contracts_batch()
        else:
            raise UserError(_('Loại thao tác không hợp lệ: %s') % self.action_type)