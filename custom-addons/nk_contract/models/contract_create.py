# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeContractCreate(models.Model):
    """
    Chức năng TẠO MỚI hợp đồng cho nhân viên
    - Chỉ áp dụng cho nhân viên CHƯA CÓ hợp đồng
    - KHÔNG kiểm tra policies
    """
    _inherit = 'hr.employee'
    
    # ========================================
    # PUBLIC METHODS - CREATE
    # ========================================
    
    def create_single_contract(self):
        """
        Tạo hợp đồng cho MỘT nhân viên
        
        Raises:
            UserError: Nếu nhân viên đã có hợp đồng
        """
        self.ensure_one()
        
        # Validation: Nhân viên PHẢI chưa có hợp đồng
        if self.contract_ids:
            raise UserError(_(
                'Nhân viên "%s" đã có hợp đồng lao động.\n\n'
                'Vui lòng sử dụng chức năng "Tái tạo hợp đồng" '
                'để tạo hợp đồng mới cho nhân viên này.'
            ) % self.name)
        
        _logger.info(f"Creating single contract for employee: {self.name}")
        
        return self.create_contracts_batch()
    
    def create_contracts_batch(self):
        """
        Tạo hợp đồng HÀNG LOẠT cho nhiều nhân viên
        
        Returns:
            dict: Action notification
            
        Raises:
            UserError: 
                - Nếu không có nhân viên nào được chọn
                - Nếu có nhân viên đã có hợp đồng
        """
        # Validation 1: Phải có nhân viên được chọn
        if not self:
            raise UserError(_(
                'Vui lòng chọn ít nhất một nhân viên để tạo hợp đồng.'
            ))
        
        # Validation 2: TẤT CẢ nhân viên phải chưa có hợp đồng
        employees_with_contract = self.filtered(lambda emp: emp.contract_ids)
        
        if employees_with_contract:
            employee_names = employees_with_contract.mapped('name')
            raise UserError(_(
                'Không thể tạo hợp đồng!\n\n'
                'Các nhân viên sau ĐÃ CÓ hợp đồng:\n%s\n\n'
                'Vui lòng:\n'
                '• Bỏ chọn các nhân viên này, HOẶC\n'
                '• Sử dụng chức năng "Tái tạo hợp đồng"'
            ) % '\n'.join([f'• {name}' for name in employee_names]))
        
        _logger.info(
            f"Starting batch contract creation for {len(self)} employees"
        )
        
        # Danh sách contracts đã tạo
        contracts_created = []
        errors = []
        
        # Loop qua từng nhân viên
        for employee in self:
            try:
                # Bước 1: Chuẩn bị contract values
                contract_vals = employee._prepare_contract_base_vals()
                
                # Bước 2: Thêm thông tin ĐẶC THÙ cho CREATE
                # Lấy department/job từ EMPLOYEE (không có contract cũ)
                if employee.department_id:
                    contract_vals['department_id'] = employee.department_id.id
                    
                if employee.job_id:
                    contract_vals['job_id'] = employee.job_id.id
                
                _logger.debug(
                    f"Creating contract for {employee.name} with vals: {contract_vals}"
                )
                
                # Bước 3: Tạo contract
                contract = employee._create_contract_record(contract_vals)
                
                contracts_created.append(contract)
                
                _logger.info(
                    f"✓ Successfully created contract {contract.name} "
                    f"for employee {employee.name}"
                )
                
            except Exception as e:
                # Lỗi không mong đợi
                error_msg = str(e)
                errors.append(f"• {employee.name}: {error_msg}")
                _logger.exception(
                    f"✗ Unexpected error creating contract for {employee.name}"
                )
        
        # Xử lý kết quả
        if errors:
            # Có lỗi xảy ra
            if contracts_created:
                # Một phần thành công, một phần thất bại
                message = _(
                    'Đã tạo %d/%d hợp đồng.\n\n'
                    'Các nhân viên sau gặp lỗi:\n%s'
                ) % (
                    len(contracts_created),
                    len(self),
                    '\n'.join(errors)
                )
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Tạo hợp đồng một phần thành công'),
                        'message': message,
                        'type': 'warning',
                        'sticky': True,
                    }
                }
            else:
                # Tất cả đều thất bại
                message = _(
                    'Không thể tạo hợp đồng cho tất cả nhân viên!\n\n'
                    'Lỗi:\n%s'
                ) % '\n'.join(errors)
                
                raise UserError(message)
        
        # Tất cả thành công
        _logger.info(
            f"✓ Batch creation completed: {len(contracts_created)} contracts created"
        )
        
        return self._show_success_notification(contracts_created, 'tạo')
    
    # ========================================
    # HELPER METHODS (Private)
    # ========================================
    
    @api.model
    def get_employees_without_contracts(self):
        """
        Lấy danh sách nhân viên CHƯA CÓ hợp đồng
        
        Returns:
            hr.employee recordset
        """
        return self.search([
            ('contract_ids', '=', False)
        ])